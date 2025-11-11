from fastapi import APIRouter, Depends, HTTPException, status # type: ignore
from sqlalchemy.orm import Session
from typing import Optional

from ..schemas import labContentSchema as schema, usersSchema
from ..controller import labContentController, userAccessController, usersController
from ..database import SessionLocal

from datetime import datetime
import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def to_wib(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return JAKARTA_TZ.localize(dt) if dt.tzinfo is None else dt.astimezone(JAKARTA_TZ)

router = APIRouter(
    prefix="/lab_contents",
    tags=["Lab Contents"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=schema.LabContentResponse)
def read_all_lab_contents(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    search: Optional[str] = None,
    
    status: Optional[int] = None,
    mappingCode: Optional[str] = None,
):
    lab_contents_data = labContentController.get_lab_contents(
        db=db, skip=skip, limit=limit, search=search, nstatus=status,
        vcode=mappingCode
    )
    return lab_contents_data