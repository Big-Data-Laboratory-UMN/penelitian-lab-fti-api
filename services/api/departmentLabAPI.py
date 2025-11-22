from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks # type: ignore
from sqlalchemy.orm import Session
from typing import Optional

from ..schemas import departmentLabSchema as schema, usersSchema
from ..schemas.departmentLabSchema import DepartmentLab
from ..controller import auditLogController
from ..controller import departmentLabController, userAccessController, usersController
from ..database import SessionLocal

from datetime import datetime
import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def to_wib(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return JAKARTA_TZ.localize(dt) if dt.tzinfo is None else dt.astimezone(JAKARTA_TZ)

router = APIRouter(
    prefix="/department_labs",
    tags=["Department Labs"]
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

@router.get("/", response_model=schema.DepartmentLabResponse)
def read_all_department_labs(
    skip: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    status: Optional[int] = None,
    nid_lab: Optional[int] = None, 
    nid_department: Optional[int] = None,
    mappingCode: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    department_labs_data = departmentLabController.get_department_labs(
        db=db, skip=skip, limit=limit, search=search, nstatus=status,nid_lab=nid_lab,
        nid_department=nid_department,
        vcode=mappingCode
    )
    return department_labs_data

@router.get("/{department_lab_id}", response_model=schema.DepartmentLab)
def get_department_lab_by_id(department_lab_id: int, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_forbidden_roles(db, current_user)
    department_lab = departmentLabController.get_department_lab(db=db, department_lab_id=department_lab_id)
    if department_lab is None:
        raise HTTPException(status_code=404, detail="Department Lab assignment not found")
    return department_lab

@router.post("/", response_model=schema.DepartmentLab, status_code=status.HTTP_201_CREATED)
def create_new_department_lab(
    department_lab: schema.DepartmentLabCreate, 
    request: Request,                 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    try:
        # Panggil controller asli
        new_dept_lab = departmentLabController.create_department_lab(db=db, department_lab=department_lab, current_user=current_user)
        
        # --- LOG ACTIVITY (BACKGROUND) ---
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="CREATE",
            target_model="DepartmentLab",
            target_identifier=new_dept_lab.vcode,
            jbefore=None,
            jafter=department_lab.model_dump(),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        # ---------------------------------
        
        return new_dept_lab
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{department_lab_vcode}", response_model=schema.DepartmentLab)
def update_existing_department_lab(
    department_lab_vcode: str, 
    department_lab: schema.DepartmentLabUpdate, 
    request: Request,                 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    
    # --- AMBIL DATA SEBELUM UPDATE ---
    db_dept_lab_before = departmentLabController.get_department_lab_by_code(db, vcode=department_lab_vcode) #
    if not db_dept_lab_before:
        raise HTTPException(status_code=404, detail="Department Lab assignment not found")
    
    # Pake mode='json' buat fix error datetime
    jbefore = DepartmentLab.model_validate(db_dept_lab_before).model_dump(mode='json')
    # ----------------------------------

    try:
        # Panggil controller asli
        db_department_lab = departmentLabController.update_department_lab(db=db, department_lab_vcode=department_lab_vcode, department_lab=department_lab, current_user=current_user)
        
        if db_department_lab is None: #
            raise HTTPException(status_code=404, detail="Department Lab assignment not found")
        
        # --- LOG ACTIVITY (BACKGROUND) ---
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="UPDATE",
            target_model="DepartmentLab",
            target_identifier=db_department_lab.vcode,
            jbefore=jbefore,
            jafter=department_lab.model_dump(),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        # ---------------------------------
        
        return db_department_lab
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{department_lab_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_department_lab(
    department_lab_vcode: str, 
    request: Request,                 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    
    # --- AMBIL DATA SEBELUM DELETE ---
    db_dept_lab_before = departmentLabController.get_department_lab_by_code(db, vcode=department_lab_vcode) #
    if not db_dept_lab_before:
        raise HTTPException(status_code=404, detail="Department Lab assignment not found")
        
    jbefore = DepartmentLab.model_validate(db_dept_lab_before).model_dump(mode='json')
    # ---------------------------------
    
    # Panggil controller asli
    deleted_dept_lab = departmentLabController.delete_department_lab(db=db, department_lab_vcode=department_lab_vcode, current_user=current_user)
    
    if deleted_dept_lab is None: #
        raise HTTPException(status_code=404, detail="Department Lab assignment not found")

    # --- BUAT 'jafter' DARI HASIL UPDATE ---
    jafter = DepartmentLab.model_validate(deleted_dept_lab).model_dump(mode='json')
    # --------------------------------------

    # --- LOG ACTIVITY (BACKGROUND) ---
    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="DELETE",
        target_model="DepartmentLab",
        target_identifier=department_lab_vcode,
        jbefore=jbefore, # Data sebelum (nstatus=1)
        jafter=jafter,   # Data sesudah (nstatus=0)
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    # ---------------------------------
    
    return

@router.get("/all-for-dropdown/", response_model=schema.DepartmentLabDropdownResponse)
def read_all_department_labs_for_dropdown(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_forbidden_roles(db, current_user)
    department_labs_data = departmentLabController.get_all_department_labs_for_dropdown(db=db)
    return department_labs_data

@router.get("/labs-by-department/{department_id}")
def get_labs_by_department(
    department_id: int, 
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user) 
    
    try:
        labs = departmentLabController.get_labs_by_department_for_dropdown(
            db=db, department_id=department_id
        )
        return labs
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Internal server error: {e}") 
        raise HTTPException(status_code=500, detail="Internal Server Error")