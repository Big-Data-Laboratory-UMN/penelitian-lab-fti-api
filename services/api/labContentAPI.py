from fastapi import APIRouter, Depends, HTTPException, status, Response # type: ignore
from sqlalchemy.orm import Session
from typing import Optional

from ..schemas import labContentSchema as schema, usersSchema
from ..controller import labContentController, userAccessController, usersController
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
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # Filter by accessible labs for non-SA users
    accessible_labs = permissions.get_accessible_labs_for_user(db, current_user.nid)
    lab_contents_data = labContentController.get_lab_contents(
        db=db, skip=skip, limit=limit, search=search, nstatus=status,
        vcode=mappingCode, accessible_lab_ids=accessible_labs
    )
    return lab_contents_data


@router.post("/", response_model=schema.LabContent, status_code=status.HTTP_201_CREATED)
def create_lab_content(
    payload: schema.LabContentCreate,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # Check if user can edit content for this lab
    if not permissions.can_edit_lab_content(db, current_user.nid, payload.nid_lab):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak memiliki akses untuk membuat konten pada lab ini."
        )
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
    # Check if user can edit content for this lab
    if not permissions.can_edit_lab_content(db, current_user.nid, payload.nid_lab):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak memiliki akses untuk mengubah konten pada lab ini."
        )
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
    # Get the content first to check lab access
    existing_content = labContentController.get_lab_content_by_vcode(db, vcode)
    if not existing_content:
        raise HTTPException(status_code=404, detail="Lab content tidak ditemukan")
    
    if not permissions.can_edit_lab_content(db, current_user.nid, existing_content.nid_lab):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak memiliki akses untuk menghapus konten pada lab ini."
        )
    
    deleted = labContentController.delete_lab_content(db=db, vcode=vcode, modified_by=current_user.vcode)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Lab content tidak ditemukan atau gagal dihapus")
    return Response(status_code=status.HTTP_204_NO_CONTENT)