from fastapi import APIRouter, Depends, HTTPException, status # type: ignore
from sqlalchemy.orm import Session
from typing import List, Optional

from ..schemas import departmentSchema as schema
from ..controller import departmentController
from ..database import SessionLocal

router = APIRouter(
    prefix="/departments",
    tags=["Departments"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=schema.DepartmentResponse)
def read_all_departments(
    skip: int = 0, 
    limit: int = 10, 
    search: Optional[str] = None, 
    departmentName: Optional[str] = None,
    departmentCode: Optional[str] = None,
    departmentDesc: Optional[str] = None,
    status: Optional[int] = None,
    db: Session = Depends(get_db)
):
    departments_data = departmentController.get_departments(
        db=db, skip=skip, limit=limit, search=search,
        vname=departmentName, vcode=departmentCode, vdesc=departmentDesc, nstatus=status
    )
    return departments_data

@router.get("/{department_id}", response_model=schema.Department)
def get_department_by_id(department_id: int, db: Session = Depends(get_db)):
    department = departmentController.get_department(db=db, department_id=department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    return department


@router.post("/", response_model=schema.Department, status_code=status.HTTP_201_CREATED)
def create_new_department(department: schema.DepartmentCreate, db: Session = Depends(get_db)):
    try:
        return departmentController.create_department(db=db, department=department)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{department_vcode}", response_model=schema.Department)
def update_existing_department(department_vcode: str, department: schema.DepartmentUpdate, db: Session = Depends(get_db)):
    try:
        db_department = departmentController.update_department(db=db, department_vcode=department_vcode, department=department)
        if db_department is None:
            raise HTTPException(status_code=404, detail="Department not found")
        return db_department
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{department_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_department(department_vcode: str, db: Session = Depends(get_db)):
    department = departmentController.delete_department(db=db, department_vcode=department_vcode)
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    return

@router.get("/all-for-dropdown/", response_model=schema.DepartmentDropdownResponse)
def read_all_departments_for_dropdown(db: Session = Depends(get_db)):
    departments_data = departmentController.get_all_departments_for_dropdown(db=db)
    return departments_data