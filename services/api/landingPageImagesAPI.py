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

ALLOWED_LANDING_PAGE_IMAGE_ROLES = {"SA", "ADM"}

def require_landing_page_image_role(db: Session, current_user: usersSchema.User):
    user_roles = set(userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid))
    if not (user_roles & ALLOWED_LANDING_PAGE_IMAGE_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role tidak diizinkan (hanya SA/ADM) untuk operasi Landing Page Image."
        )


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

@router.post("/", response_model=schema.LandingPageImage, status_code=status.HTTP_201_CREATED)
def create_home_content_file(
    image_data: schema.LandingPageImageCreate,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    require_landing_page_image_role(db, current_user)
    try:
        new_image = landingPageImagesController.create_landing_page_image(db=db, image_data=image_data, current_user=current_user)
        return new_image
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{vcode}", response_model=schema.LandingPageImage)
def update_home_content_file(
    vcode: str,
    image_data: schema.LandingPageImageUpdate,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    require_landing_page_image_role(db, current_user)
    try:
        updated_image = landingPageImagesController.update_landing_page_image(db=db, vcode=vcode, image_data=image_data, current_user=current_user)
        if not updated_image:
            raise HTTPException(status_code=404, detail="Image not found")
        return updated_image
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))