from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks, UploadFile, File as FastAPIFile, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path
import shutil
import os
import uuid

from ..schemas import labSchema as schema, usersSchema, filesSchema
from ..schemas.labSchema import Lab
from ..controller import auditLogController
from ..controller import labController, usersController, userAccessController
from ..controller import departmentLabController 
from ..schemas import departmentLabSchema 
from ..models import userAccessModel, rolesModel
from ..database import SessionLocal

import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

router = APIRouter(
    prefix="/labs",
    tags=["Labs"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
def check_forbidden_roles(db: Session, current_user: usersSchema.User):
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if "PIC" in user_roles or "VSTR" in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk operasi ini."
        )


@router.get("/", response_model=schema.LabResponse)
def read_all_labs(
    skip: int = 0, 
    limit: int = 10, 
    search: Optional[str] = None, 
    labName: Optional[str] = None,
    labCode: Optional[str] = None,
    labDesc: Optional[str] = None,
    status: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    labs_data = labController.get_labs(
        db=db, skip=skip, limit=limit, search=search,
        vname=labName, vcode=labCode, vdesc=labDesc, nstatus=status, current_user=current_user,
    )
    return labs_data

@router.get("/public/all", response_model=schema.LabPublicResponse)
def read_all_labs_public(
    skip: int = 0, 
    limit: int = 100, 
    search: Optional[str] = None, 
    db: Session = Depends(get_db)
):
    """
    Get all active labs for public view with hero image (no auth required).
    Only returns active labs (nstatus=1).
    """
    labs_data = labController.get_public_labs(
        db=db, skip=skip, limit=limit, search=search
    )
    return labs_data

@router.get("/public/{lab_vcode}", response_model=schema.LabDetail)
def get_lab_by_code_public(lab_vcode: str, db: Session = Depends(get_db)):
    """
    Get lab details by code for public view with hero/gallery images (no auth required).
    """
    # First get basic lab to find nid
    lab_basic = labController.get_lab_by_code(db=db, lab_code=lab_vcode)
    if lab_basic is None or lab_basic.nstatus != 1:
        raise HTTPException(status_code=404, detail="Lab not found or inactive")
    
    # Then get full details with images
    lab_detail = labController.get_lab(db=db, lab_id=lab_basic.nid)
    return lab_detail

@router.get("/{lab_id}", response_model=schema.LabDetail)
def get_lab_by_id(lab_id: int, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_forbidden_roles(db, current_user)
    lab = labController.get_lab(db=db, lab_id=lab_id)
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")
    return lab


@router.post("/", response_model=schema.Lab, status_code=status.HTTP_201_CREATED)
async def create_new_lab(
    vcode: str = Form(...),
    vname: str = Form(...),
    vdesc: str = Form(...),
    nid_building: int = Form(...),
    vroom_number: str = Form(...),
    ncapacity: int = Form(...),
    hero_image: UploadFile = FastAPIFile(None),
    gallery_images: List[UploadFile] = FastAPIFile(None),
    request: Request = None, 
    background_tasks: BackgroundTasks = None, 
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    
    print(f"\n[Create Lab API] Request from User: {current_user.vcode}")
    
    try:
        # Validate Max Images
        total_gallery_images = len(gallery_images) if gallery_images else 0
        if total_gallery_images > 24:
             raise HTTPException(status_code=400, detail="Maksimal 24 gambar galeri yang diperbolehkan.")

        # Prepare Lab Data
        lab_data = schema.LabCreate(
            vcode=vcode,
            vname=vname,
            vdesc=vdesc,
            nid_building=nid_building,
            vroom_number=vroom_number,
            ncapacity=ncapacity,
            vcreated_by=current_user.vcode
        )

        # Call Controller with Files
        new_lab = await labController.create_lab_with_files(
            db=db,
            lab=lab_data,
            current_user=current_user,
            request=request,
            hero_image=hero_image,
            gallery_images=gallery_images
        )
        
        # Auto Mapping Admin Dept
        admin_access = db.query(userAccessModel.UserAccess).join(
            rolesModel.Role, userAccessModel.UserAccess.nid_role == rolesModel.Role.nid
        ).filter(
            userAccessModel.UserAccess.nid_user == current_user.nid,
            rolesModel.Role.vcode == 'ADM',
            userAccessModel.UserAccess.nstatus == 1
        ).first()

        if admin_access and admin_access.nid_department:
            print(f"[AutoMap] User is Admin of Dept ID {admin_access.nid_department}. Linking Lab...")
            
            dl_vcode = f"DLAB-{uuid.uuid4().hex[:8].upper()}"
            
            dl_create_data = departmentLabSchema.DepartmentLabCreate(
                vcode=dl_vcode,
                nid_department=admin_access.nid_department,
                nid_lab=new_lab.nid,
                vcreated_by=current_user.vcode
            )
            
            departmentLabController.create_department_lab(
                db=db, 
                department_lab=dl_create_data, 
                current_user=current_user
            )
            print(f"[AutoMap] Success linking Lab {new_lab.vname} to Dept ID {admin_access.nid_department}")

        # Logging (Background Task)
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="CREATE",
            target_model="Lab",
            target_identifier=new_lab.vcode,
            jbefore=None,
            jafter=lab_data.model_dump(),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        
        return new_lab

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Error Create Lab] {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.put("/{lab_vcode}", response_model=schema.Lab)
async def update_existing_lab(
    lab_vcode: str, 
    vcode: str = Form(...),
    vname: str = Form(...),
    vdesc: str = Form(...),
    nid_building: int = Form(...),
    vroom_number: str = Form(...),
    ncapacity: int = Form(...),
    nstatus: int = Form(...),
    hero_image: UploadFile = FastAPIFile(None),
    gallery_images: List[UploadFile] = FastAPIFile(None),
    existing_gallery_vcodes: List[str] = Form(None),
    request: Request = None,                 
    background_tasks: BackgroundTasks = None, 
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    
    print(f"\n[Update Lab API] Request for Lab: {lab_vcode}")

    db_lab_before = labController.get_lab_by_code(db, lab_code=lab_vcode)
    if not db_lab_before:
        raise HTTPException(status_code=404, detail="Lab not found")
    
    jbefore = Lab.model_validate(db_lab_before).model_dump(mode='json')

    try:
        # Validate Max Images
        new_gallery_count = len(gallery_images) if gallery_images else 0
        existing_gallery_count = len(existing_gallery_vcodes) if existing_gallery_vcodes else 0
        
        if (new_gallery_count + existing_gallery_count) > 24:
             raise HTTPException(status_code=400, detail="Maksimal 24 gambar galeri yang diperbolehkan.")

        # Prepare Lab Data
        lab_data = schema.LabUpdate(
            vcode=vcode,
            vname=vname,
            vdesc=vdesc,
            nid_building=nid_building,
            vroom_number=vroom_number,
            ncapacity=ncapacity,
            nstatus=nstatus,
            vmodified_by=current_user.vcode
        )
        
        # Call Controller with Files
        db_lab = await labController.update_lab_with_files(
            db=db,
            lab_vcode=lab_vcode,
            lab=lab_data,
            current_user=current_user,
            request=request,
            hero_image=hero_image,
            gallery_images=gallery_images,
            existing_gallery_vcodes=existing_gallery_vcodes
        )
        
        if db_lab is None: 
            raise HTTPException(status_code=404, detail="Lab not found")
        
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="UPDATE",
            target_model="Lab",
            target_identifier=db_lab.vcode,
            jbefore=jbefore,
            jafter=lab_data.model_dump(),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        
        return db_lab
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Error Update Lab] {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.delete("/{lab_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_lab(
    lab_vcode: str, 
    request: Request,                 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    
    db_lab_before = labController.get_lab_by_code(db, lab_code=lab_vcode)
    if not db_lab_before:
        raise HTTPException(status_code=404, detail="Lab not found")
        
    jbefore = Lab.model_validate(db_lab_before).model_dump(mode='json')
    
    deleted_lab = labController.delete_lab(db=db, lab_vcode=lab_vcode, current_user=current_user)
    
    if deleted_lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")

    jafter = Lab.model_validate(deleted_lab).model_dump(mode='json')

    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="DELETE",
        target_model="Lab",
        target_identifier=lab_vcode,
        jbefore=jbefore,
        jafter=jafter,
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    return

@router.get("/all-for-dropdown/", response_model=schema.LabDropdownResponse)
def read_all_labs_for_dropdown(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    labs_data = labController.get_all_labs_for_dropdown(db=db)
    return labs_data

@router.get("/all-active-for-dropdown/", response_model=schema.LabDropdownResponse)
def read_all_active_labs_for_dropdown(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    labs_data = labController.get_all_active_labs_for_dropdown(db=db)
    return labs_data

@router.get("/scope-all-for-dropdown/", response_model=schema.LabDropdownResponse)
def read_scope_all_labs_for_dropdown(
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    [SCOPED] Semua Lab (Active & Inactive) sesuai departemen Admin.
    """
    check_forbidden_roles(db, current_user)
    labs_data = labController.get_scoped_labs_for_dropdown(db=db, current_user=current_user)
    return labs_data

@router.get("/scope-active-for-dropdown/", response_model=schema.LabDropdownResponse)
def read_scope_active_labs_for_dropdown(
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    [SCOPED] Lab Aktif saja sesuai departemen Admin.
    Digunakan untuk Form Input Admin yang butuh Lab.
    """
    check_forbidden_roles(db, current_user)
    labs_data = labController.get_scoped_active_labs_for_dropdown(db=db, current_user=current_user)
    return labs_data