from fastapi import APIRouter, Depends, HTTPException, status # type: ignore
from sqlalchemy.orm import Session
from typing import Optional

from ..schemas import userAccessSchema as schema
from ..controller import userAccessController
from ..database import SessionLocal

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
    db: Session = Depends(get_db)
):
    user_access_data = userAccessController.get_user_access(
        db=db, skip=skip, limit=limit, search=search, nstatus=status,nid_role=nid_role,
        nid_user=nid_user, nid_department=nid_department, nid_lab=nid_lab,
        vcode=mappingCode
    )
    return user_access_data

@router.get("/{user_access_id}", response_model=schema.UserAccess)
def get_user_access_by_id(user_access_id: int, db: Session = Depends(get_db)):
    user_access = userAccessController.get_user_access(db=db, user_access_id=user_access_id)
    if user_access is None:
        raise HTTPException(status_code=404, detail="User access assignment not found")
    return user_access

@router.post("/", response_model=schema.UserAccess, status_code=status.HTTP_201_CREATED)
def create_new_user_access(user_access: schema.UserAccessCreate, db: Session = Depends(get_db)):
    try:
        return userAccessController.create_user_access(db=db, user_access=user_access)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{user_access_vcode}", response_model=schema.UserAccess)
def update_existing_user_access(user_access_vcode: str, user_access: schema.UserAccessUpdate, db: Session = Depends(get_db)):
    try:
        db_user_access = userAccessController.update_user_access(db=db, user_access_vcode=user_access_vcode, user_access=user_access)
        if db_user_access is None:
            raise HTTPException(status_code=404, detail="User access assignment not found")
        return db_user_access
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{user_access_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_user_access(user_access_vcode: str, db: Session = Depends(get_db)):
    user_access = userAccessController.delete_user_access(db=db, user_access_vcode=user_access_vcode)
    if user_access is None:
        raise HTTPException(status_code=404, detail="User access assignment not found")
    return

@router.get("/all-for-dropdown/", response_model=schema.UserAccessDropdownResponse)
def read_all_user_access_for_dropdown(db: Session = Depends(get_db)):
    user_access_data = userAccessController.get_all_user_access_for_dropdown(db=db)
    return user_access_data