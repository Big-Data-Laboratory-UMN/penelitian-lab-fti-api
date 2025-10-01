from fastapi import APIRouter, Depends, HTTPException # type: ignore
from sqlalchemy.orm import Session
from typing import List, Optional

import schema
from ..controller import rolesController
from database import SessionLocal

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