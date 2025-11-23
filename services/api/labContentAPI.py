from fastapi import APIRouter, Depends, HTTPException, status, Response # type: ignore
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

ALLOWED_LAB_CONTENT_ROLES = {"SA", "ADM", "PIC"}

def require_lab_content_role(db: Session, current_user: usersSchema.User):
    user_roles = set(userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid))
    if not (user_roles & ALLOWED_LAB_CONTENT_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role tidak diizinkan untuk mengubah Lab Content (butuh SA/ADM/PIC)."
        )

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


@router.post("/", response_model=schema.LabContent, status_code=status.HTTP_201_CREATED)
def create_lab_content(
    payload: schema.LabContentCreate,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    require_lab_content_role(db, current_user)
    try:
        payload.vcreated_by = current_user.vcode
        return labContentController.create_lab_content(db=db, lc_data=payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{vcode}", response_model=schema.LabContent)
def update_lab_content(
    vcode: str,
    payload: schema.LabContentUpdate,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    require_lab_content_role(db, current_user)
    try:
        payload.vmodified_by = current_user.vcode
        db_lc = labContentController.update_lab_content(db=db, vcode=vcode, lc_data=payload)
        if db_lc is None:
            raise HTTPException(status_code=404, detail="Lab content tidak ditemukan")
        return db_lc
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{vcode}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lab_content(
    vcode: str,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    require_lab_content_role(db, current_user)
    deleted = labContentController.delete_lab_content(db=db, vcode=vcode, modified_by=current_user.vcode)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Lab content tidak ditemukan atau gagal dihapus")
    return Response(status_code=status.HTTP_204_NO_CONTENT)