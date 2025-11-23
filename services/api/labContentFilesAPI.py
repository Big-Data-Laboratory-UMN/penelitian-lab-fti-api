from fastapi import APIRouter, Depends, HTTPException, Response, status # type: ignore
from sqlalchemy.orm import Session
from typing import Optional

from ..schemas import labContentFilesSchema as schema, usersSchema
from ..controller import labContentFilesController, userAccessController, usersController
from ..database import SessionLocal

from datetime import datetime
import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def to_wib(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return JAKARTA_TZ.localize(dt) if dt.tzinfo is None else dt.astimezone(JAKARTA_TZ)

router = APIRouter(
    prefix="/lab_contents_file",
    tags=["Lab Contents"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/{vcode_lab_content}", response_model=schema.LabContentFilesResponse)
def get_lab_content_files(
    vcode_lab_content: str, 
    response: Response,
    db: Session = Depends(get_db),
    
):
    lab_contents_data = labContentFilesController.get_lab_content_files(
        db=db, vcode_lab_content=vcode_lab_content
    )
    if len(lab_contents_data) == 0:
        response.status_code = status.HTTP_404_NOT_FOUND
        return schema.LabContentFilesResponse(
            values=[],
            total=0
        )
    
    return schema.LabContentFilesResponse(
        values=[schema.LabContentFile(**item.__dict__) for item in lab_contents_data],
        total=len(lab_contents_data)
    )

@router.post("/", response_model=schema.LabContentFile, status_code=status.HTTP_201_CREATED)
def create_lab_content_file(
    file_data: schema.LabContentFileCreate,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    try:
        new_file = labContentFilesController.create_lab_content_file(db=db, file_data=file_data, current_user=current_user)
        return new_file
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{nid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lab_content_file(
    nid: int,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    try:
        labContentFilesController.delete_lab_content_file(db=db, nid=nid, current_user=current_user)
        return
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))