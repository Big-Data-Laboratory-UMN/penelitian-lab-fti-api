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