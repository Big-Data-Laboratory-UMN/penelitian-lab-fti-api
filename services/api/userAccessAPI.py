from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks # type: ignore
from sqlalchemy.orm import Session
from typing import Optional

from ..schemas import userAccessSchema as schema, usersSchema
from ..schemas.userAccessSchema import UserAccess
from ..controller import auditLogController
from ..controller import userAccessController, usersController
from ..database import SessionLocal

from datetime import datetime
import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def to_wib(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return JAKARTA_TZ.localize(dt) if dt.tzinfo is None else dt.astimezone(JAKARTA_TZ)

router = APIRouter(
    prefix="/user-access",
    tags=["User Access"]
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

@router.get("/", response_model=schema.UserAccessResponse)
def read_all_user_access(
    skip: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    status: Optional[int] = None,
    nid_role: Optional[int] = None, 
    nid_user: Optional[int] = None,
    nid_department: Optional[int] = None,
    nid_lab: Optional[int] = None, 
    mappingCode: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    
    user_access_data = userAccessController.get_user_access(
        db=db, 
        current_user=current_user, 
        skip=skip, 
        limit=limit, 
        search=search, 
        nstatus=status,
        nid_role=nid_role,
        nid_user=nid_user, 
        nid_department=nid_department, 
        nid_lab=nid_lab,
        vcode=mappingCode
    )
    return user_access_data

@router.get("/{user_access_id}", response_model=schema.UserAccess)
def get_user_access_by_id(user_access_id: int, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_forbidden_roles(db, current_user)
    user_access = userAccessController.get_user_access(db=db, user_access_id=user_access_id)
    if user_access is None:
        raise HTTPException(status_code=404, detail="User access assignment not found")
    return user_access

@router.post("/", response_model=schema.UserAccess, status_code=status.HTTP_201_CREATED)
def create_new_user_access(
    user_access: schema.UserAccessCreate, 
    request: Request,                 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    try:
        user_access.vcreated_by = current_user.vcode
        
        # Panggil controller asli
        new_user_access = userAccessController.create_user_access(db=db, user_access=user_access)
        
        # --- LOG ACTIVITY (BACKGROUND) ---
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="CREATE",
            target_model="UserAccess",
            target_identifier=new_user_access.vcode,
            jbefore=None,
            jafter=user_access.model_dump(),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        # ---------------------------------
        
        return new_user_access
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{user_access_vcode}", response_model=schema.UserAccess)
def update_existing_user_access(
    user_access_vcode: str, 
    user_access: schema.UserAccessUpdate, 
    request: Request,                 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    
    # --- AMBIL DATA SEBELUM UPDATE ---
    db_user_access_before = userAccessController.get_user_access_by_code(db, vcode=user_access_vcode) #
    if not db_user_access_before:
        raise HTTPException(status_code=404, detail="User access assignment not found")
    
    # Pake mode='json' buat fix error datetime
    jbefore = UserAccess.model_validate(db_user_access_before).model_dump(mode='json')
    # ----------------------------------

    try:
        user_access.vmodified_by = current_user.vcode
        
        # Panggil controller asli
        db_user_access = userAccessController.update_user_access(db=db, user_access_vcode=user_access_vcode, user_access=user_access)
        
        if db_user_access is None: #
            raise HTTPException(status_code=404, detail="User access assignment not found")
        
        # --- LOG ACTIVITY (BACKGROUND) ---
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="UPDATE",
            target_model="UserAccess",
            target_identifier=db_user_access.vcode,
            jbefore=jbefore,
            jafter=user_access.model_dump(),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        # ---------------------------------
        
        return db_user_access
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{user_access_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_user_access(
    user_access_vcode: str, 
    request: Request,                 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    
    # --- AMBIL DATA SEBELUM DELETE ---
    db_user_access_before = userAccessController.get_user_access_by_code(db, vcode=user_access_vcode) #
    if not db_user_access_before:
        raise HTTPException(status_code=404, detail="User access assignment not found")
        
    jbefore = UserAccess.model_validate(db_user_access_before).model_dump(mode='json')
    # ---------------------------------
    
    # Panggil controller asli
    deleted_user_access = userAccessController.delete_user_access(db=db, user_access_vcode=user_access_vcode, current_user=current_user.vcode)
    
    if deleted_user_access is None: #
        raise HTTPException(status_code=404, detail="User access assignment not found")

    # --- BUAT 'jafter' DARI HASIL UPDATE ---
    jafter = UserAccess.model_validate(deleted_user_access).model_dump(mode='json')
    # --------------------------------------

    # --- LOG ACTIVITY (BACKGROUND) ---
    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="DELETE",
        target_model="UserAccess",
        target_identifier=user_access_vcode,
        jbefore=jbefore, # Data sebelum (nstatus=1)
        jafter=jafter,   # Data sesudah (nstatus=0)
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    # ---------------------------------
    
    return

@router.get("/all-for-dropdown/", response_model=schema.UserAccessDropdownResponse)
def read_all_user_access_for_dropdown(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_forbidden_roles(db, current_user)
    user_access_data = userAccessController.get_all_user_access_for_dropdown(db=db)
    return user_access_data