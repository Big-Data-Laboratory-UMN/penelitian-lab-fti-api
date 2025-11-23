from fastapi import APIRouter, Depends, HTTPException, status,Request, BackgroundTasks # type: ignore
from sqlalchemy.orm import Session
from typing import List, Optional

from ..schemas import rolesSchema as schema, usersSchema
from ..schemas.rolesSchema import Role
from ..controller import auditLogController
from ..controller import rolesController, usersController, userAccessController
from ..database import SessionLocal

from datetime import datetime
import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def to_wib(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return JAKARTA_TZ.localize(dt) if dt.tzinfo is None else dt.astimezone(JAKARTA_TZ)

router = APIRouter(
    prefix="/roles",
    tags=["Roles"]
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

@router.get("/", response_model=schema.RoleResponse)
def read_all_roles(
    skip: int = 0, 
    limit: int = 10, 
    search: Optional[str] = None, 
    roleName: Optional[str] = None,
    roleCode: Optional[str] = None,
    roleDesc: Optional[str] = None,
    status: Optional[int] = None,
    db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    roles_data = rolesController.get_roles(
        db=db, skip=skip, limit=limit, search=search,
        vname=roleName, vcode=roleCode, vdesc=roleDesc, nstatus=status
    )
    return roles_data

@router.get("/{role_id}", response_model=schema.Role)
def get_role_by_id(role_id: int, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Mengambil data role spesifik berdasarkan ID.
    """
    check_forbidden_roles(db, current_user)
    role = rolesController.get_role(db=db, role_id=role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.post("/", response_model=schema.Role, status_code=status.HTTP_201_CREATED)
def create_new_role(role: schema.RoleCreate,request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Membuat role baru.
    """
    check_forbidden_roles(db, current_user)
    try:
        new_role = rolesController.create_role(db=db, role=role, current_user=current_user)
        
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="CREATE",
            target_model="Role",
            target_identifier=new_role.vcode,
            jbefore=None,
            jafter=role.model_dump(),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        
        return new_role
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{role_vcode}", response_model=schema.Role)
def update_existing_role(role_vcode: str, request: Request,background_tasks: BackgroundTasks, role: schema.RoleUpdate, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Mengupdate role berdasarkan VCODE.
    """
    check_forbidden_roles(db, current_user)
    db_role_before = rolesController.get_role_by_code(db, role_code=role_vcode) #
    if not db_role_before:
        raise HTTPException(status_code=404, detail="Role not found")
    jbefore = Role.model_validate(db_role_before).model_dump(mode='json')
    try:
        updated_role = rolesController.update_role(db=db, role_vcode=role_vcode, role=role, current_user=current_user)
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="UPDATE",
            target_model="Role",
            target_identifier=updated_role.vcode,
            jbefore=jbefore, # Data SEBELUM
            jafter=role.model_dump(), # Data BARU (dari request body)
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        return updated_role
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{role_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_role(role_vcode: str,request: Request,background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Melakukan soft delete pada role berdasarkan VCODE.
    """
    check_forbidden_roles(db, current_user)
    
    # --- AMBIL DATA SEBELUM DELETE ---
    db_role_before = rolesController.get_role_by_code(db, role_code=role_vcode) #
    if not db_role_before:
        raise HTTPException(status_code=404, detail="Role not found")
        
    # Konversi ke dict (Pake mode='json' buat fix datetime)
    jbefore = Role.model_validate(db_role_before).model_dump(mode='json')
    # ---------------------------------
    
    # Panggil controller asli lu. Ini akan me-return role yang SUDAH di-update
    updated_role = rolesController.delete_role(db=db, role_vcode=role_vcode, current_user=current_user) #
    
    if updated_role is None:
        # Ini harusnya gak kejadian kalo 'db_role_before' lolos, tapi buat jaga-jaga
        raise HTTPException(status_code=404, detail="Role not found or failed to delete")

    # --- BUAT 'jafter' DARI HASIL UPDATE ---
    # Konversi 'updated_role' (yang udah nstatus=0) ke dict
    jafter = Role.model_validate(updated_role).model_dump(mode='json')
    # --------------------------------------

    # --- LOG ACTIVITY (BACKGROUND) ---
    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="DELETE", # Kita tetep pake action 'DELETE' biar jelas
        target_model="Role",
        target_identifier=role_vcode,
        jbefore=jbefore, # Data sebelum (nstatus=1)
        jafter=jafter, # <-- UBAH INI: Data sesudah (nstatus=0)
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    # ---------------------------------
    
    return # Return 204 No Content

@router.get("/all-for-dropdown/", response_model=schema.RoleDropdownResponse)
def read_all_roles_for_dropdown(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Mengambil semua data role aktif untuk keperluan dropdown.
    """
    check_adm_sa_only(db, current_user)
    roles_data = rolesController.get_all_roles_for_dropdown(db=db)
    return roles_data

@router.get("/all-active-for-dropdown/", response_model=schema.RoleDropdownResponse)
def read_all_active_roles_for_dropdown(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Mengambil semua data role aktif untuk keperluan dropdown.
    """
    check_adm_sa_only(db, current_user)
    roles_data = rolesController.get_all_active_roles_for_dropdown(db=db)
    return roles_data

@router.get("/get-all/", response_model=List[schema.Role])
def read_all_roles_no_pagination(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Mengambil semua data role tanpa paginasi.
    """
    check_adm_sa_only(db, current_user)
    roles = rolesController.get_all_roles(db=db)
    return roles["data"]

@router.get("/scope-all-for-dropdown/", response_model=schema.RoleDropdownResponse)
def read_scope_all_roles_for_dropdown(
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    [SCOPED] Semua Role (Active & Inactive) sesuai hak akses Admin.
    - SA: All
    - ADM: VSTR & PIC Only
    """
    # check_adm_sa_only(db, current_user) # Optional
    roles_data = rolesController.get_scoped_roles_for_dropdown(db=db, current_user=current_user)
    return roles_data

@router.get("/scope-active-for-dropdown/", response_model=schema.RoleDropdownResponse)
def read_scope_active_roles_for_dropdown(
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    [SCOPED] Role Aktif Saja sesuai hak akses Admin.
    Biasanya dipakai di Form 'Add User Access'.
    """
    # check_adm_sa_only(db, current_user) # Optional
    roles_data = rolesController.get_scoped_active_roles_for_dropdown(db=db, current_user=current_user)
    return roles_data