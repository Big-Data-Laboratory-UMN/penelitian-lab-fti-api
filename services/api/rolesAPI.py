from fastapi import APIRouter, Depends, HTTPException, status # type: ignore
from sqlalchemy.orm import Session
from typing import List, Optional

from ..schemas import rolesSchema as schema, usersSchema
from ..controller import rolesController, usersController, userAccessController
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
        
def check_forbidden_roles(db: Session, current_user: usersSchema.User):
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if "PIC" in user_roles or "VSTR" in user_roles or "ADM" in user_roles:
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
def create_new_role(role: schema.RoleCreate, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Membuat role baru.
    """
    check_forbidden_roles(db, current_user)
    try:
        return rolesController.create_role(db=db, role=role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{role_vcode}", response_model=schema.Role)
def update_existing_role(role_vcode: str, role: schema.RoleUpdate, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Mengupdate role berdasarkan VCODE.
    """
    check_forbidden_roles(db, current_user)
    try:
        db_role = rolesController.update_role(db=db, role_vcode=role_vcode, role=role)
        if db_role is None:
            raise HTTPException(status_code=404, detail="Role not found")
        return db_role
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{role_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_role(role_vcode: str, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Melakukan soft delete pada role berdasarkan VCODE.
    """
    check_forbidden_roles(db, current_user)
    role = rolesController.delete_role(db=db, role_vcode=role_vcode)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    return

@router.get("/all-for-dropdown/", response_model=schema.RoleDropdownResponse)
def read_all_roles_for_dropdown(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Mengambil semua data role aktif untuk keperluan dropdown.
    """
    check_forbidden_roles(db, current_user)
    roles_data = rolesController.get_all_roles_for_dropdown(db=db)
    return roles_data

@router.get("/get-all/", response_model=List[schema.Role])
def read_all_roles_no_pagination(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Mengambil semua data role tanpa paginasi.
    """
    check_forbidden_roles(db, current_user)
    roles = rolesController.get_all_roles(db=db)
    return roles["data"]