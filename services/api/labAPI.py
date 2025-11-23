from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks # type: ignore
from sqlalchemy.orm import Session
from typing import List, Optional

from ..schemas import labSchema as schema, usersSchema
from ..schemas.labSchema import Lab
from ..controller import auditLogController
from ..controller import labController, usersController, userAccessController
from ..database import SessionLocal

import uuid 
from ..controller import departmentLabController 
from ..schemas import departmentLabSchema 
from ..models import userAccessModel, rolesModel

from datetime import datetime
import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def to_wib(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return JAKARTA_TZ.localize(dt) if dt.tzinfo is None else dt.astimezone(JAKARTA_TZ)

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

@router.get("/public/all", response_model=schema.LabResponse)
def read_all_labs_public(
    skip: int = 0, 
    limit: int = 10, 
    search: Optional[str] = None, 
    db: Session = Depends(get_db)
):
    """
    Get all active labs for public view (no auth required).
    Only returns active labs (nstatus=1).
    """
    labs_data = labController.get_labs(
        db=db, skip=skip, limit=limit, search=search,
        nstatus=1 # Force active only
    )
    return labs_data

@router.get("/public/{lab_vcode}", response_model=schema.Lab)
def get_lab_by_code_public(lab_vcode: str, db: Session = Depends(get_db)):
    """
    Get lab details by code for public view (no auth required).
    """
    lab = labController.get_lab_by_code(db=db, lab_code=lab_vcode)
    if lab is None or lab.nstatus != 1:
        raise HTTPException(status_code=404, detail="Lab not found or inactive")
    return lab

@router.get("/{lab_id}", response_model=schema.Lab)
def get_lab_by_id(lab_id: int, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_forbidden_roles(db, current_user)
    lab = labController.get_lab(db=db, lab_id=lab_id)
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")
    return lab


@router.post("/", response_model=schema.Lab, status_code=status.HTTP_201_CREATED)
def create_new_lab(
    lab: schema.LabCreate, 
    request: Request, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    
    try:
        # 1. Create Lab Baru
        lab.vcreated_by = current_user.vcode
        new_lab = labController.create_lab(db=db, lab=lab, current_user=current_user)
        
        # --- [LOGIC BARU: AUTO MAPPING ADMIN DEPT] ---
        # Cek apakah user yang create adalah ADMIN (ADM)
        admin_access = db.query(userAccessModel.UserAccess).join(
            rolesModel.Role, userAccessModel.UserAccess.nid_role == rolesModel.Role.nid
        ).filter(
            userAccessModel.UserAccess.nid_user == current_user.nid,
            rolesModel.Role.vcode == 'ADM', # Cek role ADM
            userAccessModel.UserAccess.nstatus == 1
        ).first()

        # Kalau dia Admin dan punya Departemen yg valid
        if admin_access and admin_access.nid_department:
            print(f"[AutoMap] User is Admin of Dept ID {admin_access.nid_department}. Linking Lab...")
            
            # Generate vcode unik untuk mapping, misal: DLAB-{random}
            dl_vcode = f"DLAB-{uuid.uuid4().hex[:8].upper()}"
            
            # Siapkan data schema
            dl_create_data = departmentLabSchema.DepartmentLabCreate(
                vcode=dl_vcode,
                nid_department=admin_access.nid_department,
                nid_lab=new_lab.nid, # ID Lab yang baru aja dibuat
                vcreated_by=current_user.vcode
            )
            
            # Panggil fungsi controller departmentLab yang lu request
            departmentLabController.create_department_lab(
                db=db, 
                department_lab=dl_create_data, 
                current_user=current_user
            )
            print(f"[AutoMap] Success linking Lab {new_lab.vname} to Dept ID {admin_access.nid_department}")
        # ---------------------------------------------

        # 2. Logging (Background Task)
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="CREATE",
            target_model="Lab",
            target_identifier=new_lab.vcode,
            jbefore=None,
            jafter=lab.model_dump(),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        
        return new_lab

    except ValueError as e:
        # Kalau ada error validasi (misal kode lab duplikat)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Error lain (database, dll)
        print(f"[Error Create Lab] {str(e)}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan internal server.")

@router.put("/{lab_vcode}", response_model=schema.Lab)
def update_existing_lab(
    lab_vcode: str, 
    lab: schema.LabUpdate, 
    request: Request,                 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    
    db_lab_before = labController.get_lab_by_code(db, lab_code=lab_vcode) #
    if not db_lab_before:
        raise HTTPException(status_code=404, detail="Lab not found")
    
    jbefore = Lab.model_validate(db_lab_before).model_dump(mode='json')

    try:
        lab.vmodified_by = current_user.vcode #
        
        db_lab = labController.update_lab(db=db, lab_vcode=lab_vcode, lab=lab, current_user=current_user) #
        
        if db_lab is None: 
            raise HTTPException(status_code=404, detail="Lab not found")
        
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="UPDATE",
            target_model="Lab",
            target_identifier=db_lab.vcode,
            jbefore=jbefore,
            jafter=lab.model_dump(),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        
        return db_lab
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{lab_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_lab(
    lab_vcode: str, 
    request: Request,                 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    
    # --- AMBIL DATA SEBELUM DELETE ---
    db_lab_before = labController.get_lab_by_code(db, lab_code=lab_vcode) #
    if not db_lab_before:
        raise HTTPException(status_code=404, detail="Lab not found")
        
    jbefore = Lab.model_validate(db_lab_before).model_dump(mode='json')
    # ---------------------------------
    
    # Panggil controller asli
    deleted_lab = labController.delete_lab(db=db, lab_vcode=lab_vcode, current_user=current_user) #
    
    if deleted_lab is None: #
        raise HTTPException(status_code=404, detail="Lab not found")

    # --- BUAT 'jafter' DARI HASIL UPDATE ---
    jafter = Lab.model_validate(deleted_lab).model_dump(mode='json')
    # --------------------------------------

    # --- LOG ACTIVITY (BACKGROUND) ---
    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="DELETE",
        target_model="Lab",
        target_identifier=lab_vcode,
        jbefore=jbefore, # Data sebelum (nstatus=1)
        jafter=jafter,   # Data sesudah (nstatus=0)
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    # ---------------------------------
    
    return

@router.get("/all-for-dropdown/", response_model=schema.LabDropdownResponse)
def read_all_labs_for_dropdown(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    # check_forbidden_roles(db, current_user)
    labs_data = labController.get_all_labs_for_dropdown(db=db)
    return labs_data

@router.get("/all-active-for-dropdown/", response_model=schema.LabDropdownResponse)
def read_all_labs_for_dropdown(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    # check_forbidden_roles(db, current_user)
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