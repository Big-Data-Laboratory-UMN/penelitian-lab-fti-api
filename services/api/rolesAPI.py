from fastapi import APIRouter, Depends, HTTPException # type: ignore
from sqlalchemy.orm import Session
from typing import List

import schema
from ..controller import rolesController
from database import SessionLocal

# Di sini kita definisikan prefix dan tags langsung
# Ini bikin router kita jadi "self-contained" atau mandiri
router = APIRouter(
    prefix="/roles",
    tags=["Roles"]
)

# --- Dependency untuk Database Session ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Path di sini cukup "/", karena prefix "/roles" sudah didefinisikan di atas
@router.get("/", response_model=List[schema.Role])
def get_all_roles(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    roles = rolesController.get_roles(db=db, skip=skip, limit=limit)
    return roles


@router.get("/{role_id}", response_model=schema.Role)
def get_role_by_id(role_id: int, db: Session = Depends(get_db)):
    """
    Mengambil data role spesifik berdasarkan ID.
    """
    role = rolesController.get_role(db=db, role_id=role_id)

    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")

    return role
