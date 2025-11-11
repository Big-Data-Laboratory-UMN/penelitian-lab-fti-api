from fastapi import APIRouter, Depends, HTTPException, status # type: ignore
from sqlalchemy.orm import Session
from typing import Optional

from ..schemas import landingPageSchema as schema, usersSchema
from ..controller import landingPageController, userAccessController, usersController
from ..database import SessionLocal

from datetime import datetime
import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def to_wib(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return JAKARTA_TZ.localize(dt) if dt.tzinfo is None else dt.astimezone(JAKARTA_TZ)

router = APIRouter(
    prefix="/home_data",
    tags=["Lab Contents"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=schema.LandingPageResponse)
def read_all_home_data(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    search: Optional[str] = None,
    status: Optional[int] = None,
    mappingCode: Optional[str] = None,
):
    home_contents_data = landingPageController.get_landing_pages(
        db=db, skip=skip, limit=limit, search=search, nstatus=status,
        vcode=mappingCode
    )
    return home_contents_data