from fastapi import APIRouter, Depends, HTTPException, status, Response # type: ignore
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
    tags=["Landing Page"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_forbidden_roles(db: Session, current_user: usersSchema.User):
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if "PIC" in user_roles or "VSTR" in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk operasi ini."
        )

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
    check_forbidden_roles(db, current_user)
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
    check_forbidden_roles(db, current_user)
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
    check_forbidden_roles(db, current_user)
    deleted = landingPageController.delete_landing_page(db=db, vcode=vcode, modified_by=current_user.vcode)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Landing page tidak ditemukan atau gagal dihapus")
    return Response(status_code=status.HTTP_204_NO_CONTENT)