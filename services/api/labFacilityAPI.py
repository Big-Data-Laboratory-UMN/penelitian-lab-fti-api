from fastapi import APIRouter, Depends, HTTPException, status # type: ignore
from sqlalchemy.orm import Session
from typing import Optional

from ..schemas import labFacilitySchema as schema, usersSchema
from ..controller import labFacilityController, userAccessController, usersController
from ..database import SessionLocal

router = APIRouter(
    prefix="/facility_labs",
    tags=["Facility Labs"]
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

@router.get("/", response_model=schema.FacilityLabResponse)
def read_all_facility_labs(
    skip: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    status: Optional[int] = None,
    nid_lab: Optional[int] = None, 
    nid_facility: Optional[int] = None,
    mappingCode: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    facility_labs_data = labFacilityController.get_facility_labs(
        db=db, skip=skip, limit=limit, search=search, nstatus=status,nid_lab=nid_lab,
        nid_facility=nid_facility,
        vcode=mappingCode
    )
    return facility_labs_data

@router.get("/{facility_lab_id}", response_model=schema.FacilityLab)
def get_facility_lab_by_id(facility_lab_id: int, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_forbidden_roles(db, current_user)
    facility_lab = labFacilityController.get_facility_lab(db=db, facility_lab_id=facility_lab_id)
    if facility_lab is None:
        raise HTTPException(status_code=404, detail="Facility Lab assignment not found")
    return facility_lab

@router.post("/", response_model=schema.FacilityLab, status_code=status.HTTP_201_CREATED)
def create_new_facility_lab(facility_lab: schema.FacilityLabCreate, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_forbidden_roles(db, current_user)
    try:
        return labFacilityController.create_facility_lab(db=db, facility_lab=facility_lab)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{facility_lab_vcode}", response_model=schema.FacilityLab)
def update_existing_facility_lab(facility_lab_vcode: str, facility_lab: schema.FacilityLabUpdate, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_forbidden_roles(db, current_user)
    try:
        db_facility_lab = labFacilityController.update_facility_lab(db=db, facility_lab_vcode=facility_lab_vcode, facility_lab=facility_lab)
        if db_facility_lab is None:
            raise HTTPException(status_code=404, detail="Facility Lab assignment not found")
        return db_facility_lab
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{facility_lab_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_facility_lab(facility_lab_vcode: str, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_forbidden_roles(db, current_user)
    facility_lab = labFacilityController.delete_facility_lab(db=db, facility_lab_vcode=facility_lab_vcode)
    if facility_lab is None:
        raise HTTPException(status_code=404, detail="Facility Lab assignment not found")
    return

@router.get("/all-for-dropdown/", response_model=schema.FacilityLabDropdownResponse)
def read_all_facility_labs_for_dropdown(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_forbidden_roles(db, current_user)
    facility_labs_data = labFacilityController.get_all_facility_labs_for_dropdown(db=db)
    return facility_labs_data