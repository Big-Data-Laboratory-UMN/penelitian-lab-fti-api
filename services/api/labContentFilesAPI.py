from fastapi import APIRouter, Depends, HTTPException, status # type: ignore
from sqlalchemy.orm import Session
from typing import Optional

from ..schemas import labContentSchema as schema, usersSchema
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


@router.get("/{nid_lab_content}", response_model=schema.LabContentResponse)
def get_lab_content_file(
    nid_lab_content: int, 
    db: Session = Depends(get_db),

):
    lab_contents_data = labContentFilesController.get_lab_content_file(
        db=db, nid_lab_content=nid_lab_content
    )
    return lab_contents_data