from fastapi import APIRouter, Depends, HTTPException, Response, status # type: ignore
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


@router.get("/{landing_page_vcode}", response_model=schema.LandingPageImageResponse)
def get_home_content_file(
    landing_page_vcode: str, 

    response: Response,
    db: Session = Depends(get_db),
):
    home_images_contents_data = landingPageImagesController.get_landing_page_image(
        db=db, landing_page_vcode=landing_page_vcode, nstatus=1
    )
    if home_images_contents_data is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return schema.LandingPageImageResponse(
            value=schema.LandingPageImage(
                nid=0,
                vcode="",
                nid_file=0,
                nid_landing_page_section=0,
                vlandingpage_image_to_landingpage_vcode="",
                vcreated_by=None,
                dcreated_at=None,
                vmodified_by=None,
                dmodified_at=None,
                nstatus=0
            ),
            found=False
        )
    print("GOT")
    print(home_images_contents_data)
    return schema.LandingPageImageResponse(
        value=schema.LandingPageImage(**home_images_contents_data.__dict__),
        found=True
    )