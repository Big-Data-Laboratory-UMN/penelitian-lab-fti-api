from fastapi import APIRouter, Depends, HTTPException, status # type: ignore
from sqlalchemy.orm import Session
from typing import Optional

from ..schemas import landingPageImageSchema as schema, usersSchema
from ..controller import landingPageImagesController, userAccessController, usersController
from ..database import SessionLocal

from datetime import datetime
import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def to_wib(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return JAKARTA_TZ.localize(dt) if dt.tzinfo is None else dt.astimezone(JAKARTA_TZ)

router = APIRouter(
    prefix="/home_file",
    tags=["Home Contents"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/{nid_landing_page_section}", response_model=schema.LandingPageImageResponse)
def get_home_content_file(
    nid_landing_page_section: int, 
    db: Session = Depends(get_db),

):
    home_images_contents_data = landingPageImagesController.get_landing_page_images(
        db=db, nid_landing_page_section=nid_landing_page_section
    )
    return home_images_contents_data