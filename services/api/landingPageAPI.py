from fastapi import APIRouter, Depends, HTTPException, status, Response # type: ignore
from sqlalchemy.orm import Session
from typing import Optional

from ..schemas import landingPageSchema as schema, usersSchema
from ..controller import landingPageController, usersController
from ..database import SessionLocal
from utils import permissions

from datetime import datetime
import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def to_wib(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return JAKARTA_TZ.localize(dt) if dt.tzinfo is None else dt.astimezone(JAKARTA_TZ)

router = APIRouter(
    prefix="/home_data",
    tags=["Landing Page"]
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


@router.post("/", response_model=schema.LandingPage, status_code=status.HTTP_201_CREATED)
def create_landing_page(
    payload: schema.LandingPageCreate,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    if not permissions.can_edit_landing_page(db, current_user.nid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya Super Admin yang dapat membuat Landing Page."
        )
    try:
        payload.vcreated_by = current_user.vcode
        return landingPageController.create_landing_page(db=db, lp_data=payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{vcode}", response_model=schema.LandingPage)
def update_landing_page(
    vcode: str,
    payload: schema.LandingPageUpdate,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    if not permissions.can_edit_landing_page(db, current_user.nid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya Super Admin yang dapat mengubah Landing Page."
        )
    try:
        payload.vmodified_by = current_user.vcode
        db_lp = landingPageController.update_landing_page(db=db, vcode=vcode, lp_data=payload)
        if db_lp is None:
            raise HTTPException(status_code=404, detail="Landing page tidak ditemukan")
        return db_lp
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{vcode}", status_code=status.HTTP_204_NO_CONTENT)
def delete_landing_page(
    vcode: str,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    if not permissions.can_edit_landing_page(db, current_user.nid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya Super Admin yang dapat menghapus Landing Page."
        )
    deleted = landingPageController.delete_landing_page(db=db, vcode=vcode, modified_by=current_user.vcode)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Landing page tidak ditemukan atau gagal dihapus")
    return Response(status_code=status.HTTP_204_NO_CONTENT)