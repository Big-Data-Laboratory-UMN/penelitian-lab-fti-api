from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks # type: ignore
from sqlalchemy.orm import Session
from typing import Optional

from ..schemas import labFacilitySchema as schema, usersSchema
from ..schemas.labFacilitySchema import FacilityLab
from ..controller import auditLogController
from ..controller import labFacilityController, userAccessController, usersController
from ..database import SessionLocal

from datetime import datetime
import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def to_wib(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return JAKARTA_TZ.localize(dt) if dt.tzinfo is None else dt.astimezone(JAKARTA_TZ)

router = APIRouter(
    prefix="/facility_labs",
    tags=["Facility Labs"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_forbidden_roles(db: Session, current_user: usersSchema.User):
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if "PIC" in user_roles or "VSTR" in user_roles or "ADM" in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk operasi ini."
        )

@router.get("/", response_model=schema.FacilityLabResponse)
def read_all_facility_labs(
    skip: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    status: Optional[int] = None,
    nid_lab: Optional[int] = None, 
    nid_facility: Optional[int] = None,
    mappingCode: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    facility_labs_data = labFacilityController.get_facility_labs(
        db=db, skip=skip, limit=limit, search=search, nstatus=status,nid_lab=nid_lab,
        nid_facility=nid_facility,
        vcode=mappingCode
    )
    return facility_labs_data

@router.get("/{facility_lab_id}", response_model=schema.FacilityLab)
def get_facility_lab_by_id(facility_lab_id: int, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_forbidden_roles(db, current_user)
    facility_lab = labFacilityController.get_facility_lab(db=db, facility_lab_id=facility_lab_id)
    if facility_lab is None:
        raise HTTPException(status_code=404, detail="Facility Lab assignment not found")
    return facility_lab

@router.post("/", response_model=schema.FacilityLab, status_code=status.HTTP_201_CREATED)
def create_new_facility_lab(
    facility_lab: schema.FacilityLabCreate, 
    request: Request,                 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    try:
        facility_lab.vcreated_by = current_user.vcode
        
        # Panggil controller asli
        new_facility_lab = labFacilityController.create_facility_lab(db=db, facility_lab=facility_lab)
        
        # --- LOG ACTIVITY (BACKGROUND) ---
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="CREATE",
            target_model="LabFacility",
            target_identifier=new_facility_lab.vcode,
            jbefore=None,
            jafter=facility_lab.model_dump(),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        # ---------------------------------
        
        return new_facility_lab
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{facility_lab_vcode}", response_model=schema.FacilityLab)
def update_existing_facility_lab(
    facility_lab_vcode: str, 
    facility_lab: schema.FacilityLabUpdate, 
    request: Request,                 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    
    # --- AMBIL DATA SEBELUM UPDATE ---
    db_facility_lab_before = labFacilityController.get_facility_lab_by_code(db, vcode=facility_lab_vcode) #
    if not db_facility_lab_before:
        raise HTTPException(status_code=404, detail="Facility Lab assignment not found")
    
    # Pake mode='json' buat fix error datetime
    jbefore = FacilityLab.model_validate(db_facility_lab_before).model_dump(mode='json')
    # ----------------------------------

    try:
        facility_lab.vmodified_by = current_user.vcode
        
        # Panggil controller asli
        db_facility_lab = labFacilityController.update_facility_lab(db=db, facility_lab_vcode=facility_lab_vcode, facility_lab=facility_lab)
        
        if db_facility_lab is None: #
            raise HTTPException(status_code=404, detail="Facility Lab assignment not found")
        
        # --- LOG ACTIVITY (BACKGROUND) ---
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="UPDATE",
            target_model="LabFacility",
            target_identifier=db_facility_lab.vcode,
            jbefore=jbefore,
            jafter=facility_lab.model_dump(),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        # ---------------------------------
        
        return db_facility_lab
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{facility_lab_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_facility_lab(
    facility_lab_vcode: str, 
    request: Request,                 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    
    # --- AMBIL DATA SEBELUM DELETE ---
    db_facility_lab_before = labFacilityController.get_facility_lab_by_code(db, vcode=facility_lab_vcode) #
    if not db_facility_lab_before:
        raise HTTPException(status_code=404, detail="Facility Lab assignment not found")
        
    jbefore = FacilityLab.model_validate(db_facility_lab_before).model_dump(mode='json')
    # ---------------------------------
    
    # Panggil controller asli
    deleted_facility_lab = labFacilityController.delete_facility_lab(db=db, facility_lab_vcode=facility_lab_vcode, current_user=current_user.vcode)
    
    if deleted_facility_lab is None: #
        raise HTTPException(status_code=404, detail="Facility Lab assignment not found")

    # --- BUAT 'jafter' DARI HASIL UPDATE ---
    jafter = FacilityLab.model_validate(deleted_facility_lab).model_dump(mode='json')
    # --------------------------------------

    # --- LOG ACTIVITY (BACKGROUND) ---
    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="DELETE",
        target_model="LabFacility",
        target_identifier=facility_lab_vcode,
        jbefore=jbefore, # Data sebelum (nstatus=1)
        jafter=jafter,   # Data sesudah (nstatus=0)
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    # ---------------------------------
    
    return

@router.get("/all-for-dropdown/", response_model=schema.FacilityLabDropdownResponse)
def read_all_facility_labs_for_dropdown(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_forbidden_roles(db, current_user)
    facility_labs_data = labFacilityController.get_all_facility_labs_for_dropdown(db=db)
    return facility_labs_data

@router.get("/facilities-by-labs/{lab_id}")
def get_labs_by_department(
    lab_id: int, 
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # check_forbidden_roles(db, current_user) 
    
    try:
        facilities = labFacilityController.get_facilities_by_labs_for_dropdown(
            db=db, lab_id=lab_id
        )
        return facilities
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Internal server error: {e}") 
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/anonymous/lab/{lab_vcode}", response_model=schema.FacilityLabAnonymousResponse)
def get_facilities_by_lab_anonymous(
    lab_vcode: str,
    db: Session = Depends(get_db)
):
    """
    Get facilities for a lab anonymously by lab vcode.
    Returns LabFacility objects with facility details.
    """
    try:
        results = labFacilityController.get_facilities_by_lab_code_anonymous(db=db, lab_vcode=lab_vcode)
        if results is None:
             raise HTTPException(status_code=404, detail="Lab not found")
        
        # Format to match FacilityLabAnonymousResponse
        formatted_data = []
        for lab_facility, facility_name, facility_desc, facility_nid_file in results:
            formatted_data.append({
                "nid": lab_facility.nid,
                "vcode": lab_facility.vcode,
                "vcode_facility": lab_facility.vcode_facility,
                "vname": facility_name,
                "vdesc": facility_desc,
                "nid_file": facility_nid_file
            })
            
        return {"data": formatted_data, "total": len(formatted_data)}
    except Exception as e:
        print(f"Error getting facilities anonymously: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")