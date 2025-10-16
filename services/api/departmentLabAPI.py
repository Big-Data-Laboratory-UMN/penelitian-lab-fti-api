from fastapi import APIRouter, Depends, HTTPException, status # type: ignore
from sqlalchemy.orm import Session
from typing import Optional

from ..schemas import departmentLabSchema as schema
from ..controller import departmentLabController
from ..database import SessionLocal

router = APIRouter(
    prefix="/department_labs",
    tags=["Department Labs"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=schema.DepartmentLabResponse)
def read_all_department_labs(
    skip: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    status: Optional[int] = None,
    nid_lab: Optional[int] = None, 
    nid_department: Optional[int] = None,
    mappingCode: Optional[str] = None,
    db: Session = Depends(get_db)
):
    department_labs_data = departmentLabController.get_department_labs(
        db=db, skip=skip, limit=limit, search=search, nstatus=status,nid_lab=nid_lab,
        nid_department=nid_department,
        vcode=mappingCode
    )
    return department_labs_data

@router.get("/{department_lab_id}", response_model=schema.DepartmentLab)
def get_department_lab_by_id(department_lab_id: int, db: Session = Depends(get_db)):
    department_lab = departmentLabController.get_department_lab(db=db, department_lab_id=department_lab_id)
    if department_lab is None:
        raise HTTPException(status_code=404, detail="Department Lab assignment not found")
    return department_lab

@router.post("/", response_model=schema.DepartmentLab, status_code=status.HTTP_201_CREATED)
def create_new_department_lab(department_lab: schema.DepartmentLabCreate, db: Session = Depends(get_db)):
    try:
        return departmentLabController.create_department_lab(db=db, department_lab=department_lab)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{department_lab_vcode}", response_model=schema.DepartmentLab)
def update_existing_department_lab(department_lab_vcode: str, department_lab: schema.DepartmentLabUpdate, db: Session = Depends(get_db)):
    try:
        db_department_lab = departmentLabController.update_department_lab(db=db, department_lab_vcode=department_lab_vcode, department_lab=department_lab)
        if db_department_lab is None:
            raise HTTPException(status_code=404, detail="Department Lab assignment not found")
        return db_department_lab
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{department_lab_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_department_lab(department_lab_vcode: str, db: Session = Depends(get_db)):
    department_lab = departmentLabController.delete_department_lab(db=db, department_lab_vcode=department_lab_vcode)
    if department_lab is None:
        raise HTTPException(status_code=404, detail="Department Lab assignment not found")
    return

@router.get("/all-for-dropdown/", response_model=schema.DepartmentLabDropdownResponse)
def read_all_department_labs_for_dropdown(db: Session = Depends(get_db)):
    department_labs_data = departmentLabController.get_all_department_labs_for_dropdown(db=db)
    return department_labs_data