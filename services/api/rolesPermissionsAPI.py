from fastapi import APIRouter, Depends, HTTPException, status # type: ignore
from sqlalchemy.orm import Session
from typing import Optional

from ..schemas import rolesPermissionsSchema as schema, usersSchema
from ..controller import rolesPermissionsController, userAccessController, usersController
from ..database import SessionLocal

from datetime import datetime
import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def to_wib(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return JAKARTA_TZ.localize(dt) if dt.tzinfo is None else dt.astimezone(JAKARTA_TZ)

router = APIRouter(
    prefix="/roles-permissions",
    tags=["Roles Permissions"]
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

@router.get("/", response_model=schema.RolePermissionResponse)
def read_all_roles_permissions(
    skip: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    status: Optional[int] = None,
    nid_role: Optional[int] = None, 
    nid_permission: Optional[int] = None,
    mappingCode: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Mengambil semua data relasi role-permission dengan paginasi dan filter.
    """
    check_forbidden_roles(db, current_user)
    roles_permissions_data = rolesPermissionsController.get_roles_permissions(
        db=db, skip=skip, limit=limit, search=search, nstatus=status,nid_role=nid_role,
        nid_permission=nid_permission,
        vcode=mappingCode
    )
    return roles_permissions_data

@router.get("/{role_permission_id}", response_model=schema.RolePermission)
def get_role_permission_by_id(role_permission_id: int, db: Session = Depends(get_db),  current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Mengambil data relasi role-permission spesifik berdasarkan ID.
    """
    check_forbidden_roles(db, current_user)
    role_permission = rolesPermissionsController.get_role_permission(db=db, role_permission_id=role_permission_id)
    if role_permission is None:
        raise HTTPException(status_code=404, detail="Role Permission assignment not found")
    return role_permission

@router.post("/", response_model=schema.RolePermission, status_code=status.HTTP_201_CREATED)
def create_new_role_permission(role_permission: schema.RolePermissionCreate, db: Session = Depends(get_db),  current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Membuat relasi role-permission baru.
    """
    check_forbidden_roles(db, current_user)
    try:
        return rolesPermissionsController.create_role_permission(db=db, role_permission=role_permission)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{role_permission_vcode}", response_model=schema.RolePermission)
def update_existing_role_permission(role_permission_vcode: str, role_permission: schema.RolePermissionUpdate, db: Session = Depends(get_db),  current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Mengupdate relasi role-permission berdasarkan VCODE.
    """
    check_forbidden_roles(db, current_user)
    try:
        db_role_permission = rolesPermissionsController.update_role_permission(db=db, role_permission_vcode=role_permission_vcode, role_permission=role_permission)
        if db_role_permission is None:
            raise HTTPException(status_code=404, detail="Role Permission assignment not found")
        return db_role_permission
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{role_permission_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_role_permission(role_permission_vcode: str, db: Session = Depends(get_db),  current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Melakukan soft delete pada relasi role-permission berdasarkan VCODE.
    """
    check_forbidden_roles(db, current_user)
    role_permission = rolesPermissionsController.delete_role_permission(db=db, role_permission_vcode=role_permission_vcode)
    if role_permission is None:
        raise HTTPException(status_code=404, detail="Role Permission assignment not found")
    return

@router.get("/all-for-dropdown/", response_model=schema.RolePermissionDropdownResponse)
def read_all_roles_permissions_for_dropdown(db: Session = Depends(get_db),  current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Mengambil semua data relasi role-permission aktif untuk keperluan dropdown.
    """
    check_forbidden_roles(db, current_user)
    roles_permissions_data = rolesPermissionsController.get_all_roles_permissions_for_dropdown(db=db)
    return roles_permissions_data