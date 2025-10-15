from fastapi import APIRouter, Depends, HTTPException, status # type: ignore
from sqlalchemy.orm import Session
from typing import List, Optional

from ..schemas import labSchema as schema
from ..controller import labController
from ..database import SessionLocal

router = APIRouter(
    prefix="/labs",
    tags=["Labs"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=schema.LabResponse)
def read_all_labs(
    skip: int = 0, 
    limit: int = 10, 
    search: Optional[str] = None, 
    labName: Optional[str] = None,
    labCode: Optional[str] = None,
    labDesc: Optional[str] = None,
    status: Optional[int] = None,
    db: Session = Depends(get_db)
):
    labs_data = labController.get_labs(
        db=db, skip=skip, limit=limit, search=search,
        vname=labName, vcode=labCode, vdesc=labDesc, nstatus=status
    )
    return labs_data

@router.get("/{lab_id}", response_model=schema.Lab)
def get_lab_by_id(lab_id: int, db: Session = Depends(get_db)):
    lab = labController.get_lab(db=db, lab_id=lab_id)
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")
    return lab


@router.post("/", response_model=schema.Lab, status_code=status.HTTP_201_CREATED)
def create_new_lab(lab: schema.LabCreate, db: Session = Depends(get_db)):
    try:
        return labController.create_lab(db=db, lab=lab)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{lab_vcode}", response_model=schema.Lab)
def update_existing_lab(lab_vcode: str, lab: schema.LabUpdate, db: Session = Depends(get_db)):
    try:
        db_lab = labController.update_lab(db=db, lab_vcode=lab_vcode, lab=lab)
        if db_lab is None:
            raise HTTPException(status_code=404, detail="Lab not found")
        return db_lab
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{lab_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_lab(lab_vcode: str, db: Session = Depends(get_db)):
    lab = labController.delete_lab(db=db, lab_vcode=lab_vcode)
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")
    return

@router.get("/all-for-dropdown/", response_model=schema.LabDropdownResponse)
def read_all_labs_for_dropdown(db: Session = Depends(get_db)):
    labs_data = labController.get_all_labs_for_dropdown(db=db)
    return labs_data