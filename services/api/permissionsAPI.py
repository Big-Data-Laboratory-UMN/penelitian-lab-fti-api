from fastapi import APIRouter, Depends, HTTPException, status # type: ignore
from sqlalchemy.orm import Session
from typing import List, Optional

from ..schemas import permissionsSchema as schema
from ..controller import permissionsController
from ..database import SessionLocal

router = APIRouter(
    prefix="/permissions",
    tags=["Permissions"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=schema.PermissionResponse)
def read_all_permissions(
    skip: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    permissionName: Optional[str] = None,
    permissionCode: Optional[str] = None,
    permissionDesc: Optional[str] = None,
    status: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Mengambil semua data permissions dengan paginasi, pencarian, dan filter.
    """
    permissions_data = permissionsController.get_permissions(
        db=db, skip=skip, limit=limit, search=search,
        vname=permissionName, vcode=permissionCode, vdesc=permissionDesc, nstatus=status
    )
    return permissions_data


@router.get("/{permission_id}", response_model=schema.Permission)
def get_permission_by_id(permission_id: int, db: Session = Depends(get_db)):
    """
    Mengambil data permission spesifik berdasarkan ID.
    """
    permission = permissionsController.get_permission(db=db, permission_id=permission_id)
    if permission is None:
        raise HTTPException(status_code=404, detail="Permission not found")
    return permission


@router.post("/", response_model=schema.Permission, status_code=status.HTTP_201_CREATED)
def create_new_permission(permission: schema.PermissionCreate, db: Session = Depends(get_db)):
    """
    Membuat permission baru.
    """
    try:
        return permissionsController.create_permission(db=db, permission=permission)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{permission_vcode}", response_model=schema.Permission)
def update_existing_permission(permission_vcode: str, permission: schema.PermissionUpdate, db: Session = Depends(get_db)):
    """
    Mengupdate permission berdasarkan VCODE.
    """
    try:
        db_permission = permissionsController.update_permission(db=db, permission_vcode=permission_vcode, permission=permission)
        if db_permission is None:
            raise HTTPException(status_code=404, detail="Permission not found")
        return db_permission
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{permission_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_permission(permission_vcode: str, db: Session = Depends(get_db)):
    """
    Melakukan soft delete pada permission berdasarkan VCODE.
    """
    permission = permissionsController.delete_permission(db=db, permission_vcode=permission_vcode)
    if permission is None:
        raise HTTPException(status_code=404, detail="Permission not found")
    return


@router.get("/all-for-dropdown/", response_model=schema.PermissionDropdownResponse)
def read_all_permissions_for_dropdown(db: Session = Depends(get_db)):
    """
    Mengambil semua data permission aktif untuk keperluan dropdown.
    """
    permissions_data = permissionsController.get_all_permissions_for_dropdown(db=db)
    return permissions_data