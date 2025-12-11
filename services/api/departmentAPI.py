from fastapi import APIRouter, Depends, HTTPException, status,Request, BackgroundTasks # type: ignore
from sqlalchemy.orm import Session
from typing import List, Optional

from ..schemas import departmentSchema as schema, usersSchema
from ..schemas.departmentSchema import Department
from ..controller import departmentController, userAccessController, usersController
from ..controller import auditLogController
from ..database import SessionLocal

from datetime import datetime
import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def to_wib(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return JAKARTA_TZ.localize(dt) if dt.tzinfo is None else dt.astimezone(JAKARTA_TZ)

router = APIRouter(
    prefix="/departments",
    tags=["Departments"]
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
        
def check_adm_sa_only(db: Session, current_user: usersSchema.User):
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if "PIC" in user_roles or "VSTR" in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk operasi ini."
        )

@router.get("/", response_model=schema.DepartmentResponse)
def read_all_departments(
    skip: int = 0, 
    limit: int = 10, 
    search: Optional[str] = None, 
    departmentName: Optional[str] = None,
    departmentCode: Optional[str] = None,
    departmentDesc: Optional[str] = None,
    status: Optional[int] = None,
    db: Session = Depends(get_db),  current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    departments_data = departmentController.get_departments(
        db=db, skip=skip, limit=limit, search=search,
        vname=departmentName, vcode=departmentCode, vdesc=departmentDesc, nstatus=status
    )
    return departments_data

@router.get("/{department_id}", response_model=schema.Department)
def get_department_by_id(department_id: int, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_forbidden_roles(db, current_user)
    department = departmentController.get_department(db=db, department_id=department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    return department


@router.post("/", response_model=schema.Department, status_code=status.HTTP_201_CREATED)
def create_new_department(
    department: schema.DepartmentCreate, 
    request: Request,                 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    try:
        # Panggil controller asli
        new_department = departmentController.create_department(db=db, department=department, current_user=current_user)
        
        # --- LOG ACTIVITY (BACKGROUND) ---
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="CREATE",
            target_model="Department",
            target_identifier=new_department.vcode,
            jbefore=None,
            jafter=department.model_dump(),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        # ---------------------------------
        
        return new_department
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{department_vcode}", response_model=schema.Department)
def update_existing_department(
    department_vcode: str, 
    department: schema.DepartmentUpdate, 
    request: Request,                 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    
    # --- AMBIL DATA SEBELUM UPDATE ---
    db_department_before = departmentController.get_department_by_code(db, department_code=department_vcode) #
    if not db_department_before:
        raise HTTPException(status_code=404, detail="Department not found")
    
    # Pake mode='json' buat fix error datetime
    jbefore = Department.model_validate(db_department_before).model_dump(mode='json')
    # ----------------------------------

    try:
        # Panggil controller asli
        db_department = departmentController.update_department(db=db, department_vcode=department_vcode, department=department, current_user=current_user)
        
        if db_department is None: #
            raise HTTPException(status_code=404, detail="Department not found")
        
        # --- LOG ACTIVITY (BACKGROUND) ---
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="UPDATE",
            target_model="Department",
            target_identifier=db_department.vcode,
            jbefore=jbefore,
            jafter=department.model_dump(),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        # ---------------------------------
        
        return db_department
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{department_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_department(
    department_vcode: str, 
    request: Request,                 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    
    # --- AMBIL DATA SEBELUM DELETE ---
    db_department_before = departmentController.get_department_by_code(db, department_code=department_vcode) #
    if not db_department_before:
        raise HTTPException(status_code=404, detail="Department not found")
        
    jbefore = Department.model_validate(db_department_before).model_dump(mode='json')
    # ---------------------------------
    
    # Panggil controller asli
    deleted_department = departmentController.delete_department(db=db, department_vcode=department_vcode, current_user=current_user)
    
    if deleted_department is None: #
        raise HTTPException(status_code=404, detail="Department not found")

    # --- BUAT 'jafter' DARI HASIL UPDATE ---
    jafter = Department.model_validate(deleted_department).model_dump(mode='json')
    # --------------------------------------

    # --- LOG ACTIVITY (BACKGROUND) ---
    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="DELETE",
        target_model="Department",
        target_identifier=department_vcode,
        jbefore=jbefore, # Data sebelum (nstatus=1)
        jafter=jafter,   # Data sesudah (nstatus=0)
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    # ---------------------------------
    
    return

@router.get("/all-for-dropdown/", response_model=schema.DepartmentDropdownResponse)
def read_all_departments_for_dropdown(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_adm_sa_only(db, current_user)
    departments_data = departmentController.get_all_departments_for_dropdown(db=db)
    return departments_data


@router.get("/all-active-for-dropdown/", response_model=schema.DepartmentDropdownResponse)
def read_all_departments_for_dropdown(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_adm_sa_only(db, current_user)
    departments_data = departmentController.get_all_active_departments_for_dropdown(db=db)
    return departments_data

@router.get("/all-active-for-user-dropdown/", response_model=schema.DepartmentDropdownResponse)
def read_all_departments_for_dropdown(db: Session = Depends(get_db)):
    # check_adm_sa_only(db, current_user)
    departments_data = departmentController.get_all_active_departments_for_dropdown(db=db, for_user=True)
    return departments_data

@router.get("/scope-all-for-dropdown/", response_model=schema.DepartmentDropdownResponse)
def read_scope_all_departments_for_dropdown(
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    [SCOPED] Semua Department (Active/Inactive) sesuai Admin.
    - SA: All.
    - ADM: Only their department.
    """
    # check_adm_sa_only(db, current_user)
    departments_data = departmentController.get_scoped_departments_for_dropdown(db=db, current_user=current_user)
    return departments_data

@router.get("/scope-active-for-dropdown/", response_model=schema.DepartmentDropdownResponse)
def read_scope_active_departments_for_dropdown(
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    [SCOPED] Department Aktif saja sesuai Admin.
    """
    # check_adm_sa_only(db, current_user)
    departments_data = departmentController.get_scoped_active_departments_for_dropdown(db=db, current_user=current_user)
    return departments_data

@router.get("/public/all-active", response_model=schema.DepartmentDropdownResponse)
def read_public_active_departments(db: Session = Depends(get_db)):
    """
    Get all active departments for public view (no auth required).
    Excludes faculty-level departments from filter display.
    """
    departments_data = departmentController.get_all_active_departments_for_dropdown(db=db)
    
    excluded_names = ["fakultas teknik dan informatika", "fakultas teknik & informatika"]
    filtered_data = [d for d in departments_data["data"] if d.vname.lower() not in excluded_names]
    
    return {"data": filtered_data}