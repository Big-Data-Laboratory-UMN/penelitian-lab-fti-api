from fastapi import APIRouter, Depends, HTTPException, status # type: ignore
from sqlalchemy.orm import Session
from typing import Optional

from ..schemas import rolesPermissionsSchema as schema
from ..controller import rolesPermissionsController
from ..database import SessionLocal

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

@router.get("/", response_model=schema.RolePermissionResponse)
def read_all_roles_permissions(
    skip: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    status: Optional[int] = None,
    nid_role: Optional[int] = None, 
    nid_permission: Optional[int] = None,
    mappingCode: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Mengambil semua data relasi role-permission dengan paginasi dan filter.
    """
    roles_permissions_data = rolesPermissionsController.get_roles_permissions(
        db=db, skip=skip, limit=limit, search=search, nstatus=status,nid_role=nid_role,
        nid_permission=nid_permission,
        vcode=mappingCode
    )
    return roles_permissions_data

@router.get("/{role_permission_id}", response_model=schema.RolePermission)
def get_role_permission_by_id(role_permission_id: int, db: Session = Depends(get_db)):
    """
    Mengambil data relasi role-permission spesifik berdasarkan ID.
    """
    role_permission = rolesPermissionsController.get_role_permission(db=db, role_permission_id=role_permission_id)
    if role_permission is None:
        raise HTTPException(status_code=404, detail="Role Permission assignment not found")
    return role_permission

@router.post("/", response_model=schema.RolePermission, status_code=status.HTTP_201_CREATED)
def create_new_role_permission(role_permission: schema.RolePermissionCreate, db: Session = Depends(get_db)):
    """
    Membuat relasi role-permission baru.
    """
    try:
        return rolesPermissionsController.create_role_permission(db=db, role_permission=role_permission)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{role_permission_vcode}", response_model=schema.RolePermission)
def update_existing_role_permission(role_permission_vcode: str, role_permission: schema.RolePermissionUpdate, db: Session = Depends(get_db)):
    """
    Mengupdate relasi role-permission berdasarkan VCODE.
    """
    try:
        db_role_permission = rolesPermissionsController.update_role_permission(db=db, role_permission_vcode=role_permission_vcode, role_permission=role_permission)
        if db_role_permission is None:
            raise HTTPException(status_code=404, detail="Role Permission assignment not found")
        return db_role_permission
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{role_permission_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_role_permission(role_permission_vcode: str, db: Session = Depends(get_db)):
    """
    Melakukan soft delete pada relasi role-permission berdasarkan VCODE.
    """
    role_permission = rolesPermissionsController.delete_role_permission(db=db, role_permission_vcode=role_permission_vcode)
    if role_permission is None:
        raise HTTPException(status_code=404, detail="Role Permission assignment not found")
    return

@router.get("/all-for-dropdown/", response_model=schema.RolePermissionDropdownResponse)
def read_all_roles_permissions_for_dropdown(db: Session = Depends(get_db)):
    """
    Mengambil semua data relasi role-permission aktif untuk keperluan dropdown.
    """
    roles_permissions_data = rolesPermissionsController.get_all_roles_permissions_for_dropdown(db=db)
    return roles_permissions_data