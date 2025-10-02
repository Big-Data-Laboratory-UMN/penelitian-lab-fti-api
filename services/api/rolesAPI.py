from fastapi import APIRouter, Depends, HTTPException, status  # type: ignore
from sqlalchemy.orm import Session
from typing import List, Optional

from ..schemas import rolesSchema as schema
from ..controller import rolesController
from ..database import SessionLocal

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

@router.get("/", response_model=schema.RoleResponse)
def read_all_roles(
    skip: int = 0, 
    limit: int = 10, 
    search: Optional[str] = None, 
    roleName: Optional[str] = None,
    roleCode: Optional[str] = None,
    roleDesc: Optional[str] = None,
    status: Optional[int] = None,
    db: Session = Depends(get_db)
):
    roles_data = rolesController.get_roles(
        db=db, skip=skip, limit=limit, search=search,
        vname=roleName, vcode=roleCode, vdesc=roleDesc, nstatus=status
    )
    return roles_data

@router.get("/{role_id}", response_model=schema.Role)
def get_role_by_id(role_id: int, db: Session = Depends(get_db)):
    """
    Mengambil data role spesifik berdasarkan ID.
    """
    role = rolesController.get_role(db=db, role_id=role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.post("/", response_model=schema.Role, status_code=status.HTTP_201_CREATED)
def create_new_role(role: schema.RoleCreate, db: Session = Depends(get_db)):
    """
    Membuat role baru.
    """
    # Cek apakah role code sudah ada
    db_role = rolesController.get_role_by_code(db, role_code=role.vcode)
    if db_role:
        raise HTTPException(status_code=400, detail="Role Code already registered")
    return rolesController.create_role(db=db, role=role)

@router.put("/{role_id}", response_model=schema.Role)
def update_existing_role(role_id: int, role: schema.RoleUpdate, db: Session = Depends(get_db)):
    """
    Mengupdate role berdasarkan ID.
    """
    db_role = rolesController.update_role(db=db, role_id=role_id, role=role)
    if db_role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    return db_role

@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_role(role_id: int, db: Session = Depends(get_db)):
    """
    Melakukan soft delete pada role berdasarkan ID.
    """
    role = rolesController.delete_role(db=db, role_id=role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    return

@router.get("/all-for-dropdown/", response_model=schema.RoleDropdownResponse)
def read_all_roles_for_dropdown(db: Session = Depends(get_db)):
    """
    Mengambil semua data role aktif untuk keperluan dropdown.
    """
    roles_data = rolesController.get_all_roles_for_dropdown(db=db)
    return roles_data