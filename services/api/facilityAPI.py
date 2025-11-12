# services/api/facilityAPI.py

from fastapi import (
    APIRouter, Depends, HTTPException, status,
    UploadFile, File, Form, Response, Request # Import Request
)
from sqlalchemy.orm import Session
from typing import List, Optional

from ..schemas import facilitySchema as schema, usersSchema
from ..controller import facilityController, usersController, userAccessController
from ..database import SessionLocal

from datetime import datetime
import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def to_wib(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return JAKARTA_TZ.localize(dt) if dt.tzinfo is None else dt.astimezone(JAKARTA_TZ)

router = APIRouter(
    prefix="/facilities",
    tags=["Facilities"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_forbidden_roles(db: Session, current_user: usersSchema.User):
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    # Sesuaikan role yang dilarang
    if "PIC" in user_roles or "VSTR" in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk operasi ini."
        )

# --- Endpoint CRUD ---

@router.get("/", response_model=schema.FacilityResponse)
def read_all_facilities(
    skip: int = 0, limit: int = 10, search: Optional[str] = None,
    facilityName: Optional[str] = None, facilityCode: Optional[str] = None,
    facilityDesc: Optional[str] = None, status: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    facilities_data = facilityController.get_facilities(
        db=db, skip=skip, limit=limit, search=search,
        vname=facilityName, vcode=facilityCode, vdesc=facilityDesc, nstatus=status
    )
    return facilities_data

@router.get("/{facility_id}", response_model=schema.Facility)
def get_facility_by_id(
    facility_id: int, db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    facility = facilityController.get_facility(db=db, facility_id=facility_id)
    if facility is None:
        raise HTTPException(status_code=404, detail="Fasilitas tidak ditemukan")
    return facility

@router.post("/", response_model=schema.Facility, status_code=status.HTTP_201_CREATED)
async def create_new_facility_with_file(
    request: Request, 
    vcode: str = Form(...),
    vname: str = Form(...),
    vdesc: str = Form(...),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    try:
        facility_data = schema.FacilityCreate(
            vcode=vcode, vname=vname, vdesc=vdesc,
            vcreated_by=current_user.vcode
        )
        # Pass request ke controller
        return await facilityController.create_facility_with_file(
            db=db, facility_data=facility_data, file=file,
            current_user=current_user, request=request # Pass request
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Unexpected error creating facility: {e}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan internal saat membuat fasilitas.")


@router.put("/{facility_vcode}", response_model=schema.Facility)
async def update_existing_facility_with_file(
    request: Request,
    facility_vcode: str,
    vcode: str = Form(...),
    vname: str = Form(...),
    vdesc: str = Form(...),
    nstatus: int = Form(...),
    nid_file: Optional[int] = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    try:
        facility_data = schema.FacilityUpdate(
            vcode=vcode, vname=vname, vdesc=vdesc, nstatus=nstatus,
            nid_file=nid_file, vmodified_by=current_user.vcode
        )
        # Pass request ke controller
        db_facility = await facilityController.update_facility_with_file(
            db=db, facility_vcode=facility_vcode, facility_data=facility_data, file=file,
            current_user=current_user, request=request # Pass request
        )
        if db_facility is None:
            raise HTTPException(status_code=404, detail="Fasilitas tidak ditemukan")
        return db_facility
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Unexpected error updating facility {facility_vcode}: {e}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan internal saat memperbarui fasilitas.")

@router.delete("/{facility_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_facility(
    facility_vcode: str, db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    try:
        deleted_facility = facilityController.delete_facility(
            db=db, facility_vcode=facility_vcode, modified_by=current_user.vcode
        )
        if deleted_facility is None:
            raise HTTPException(status_code=404, detail="Fasilitas tidak ditemukan")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Unexpected error deleting facility {facility_vcode}: {e}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan internal saat menghapus fasilitas.")

@router.get("/all-for-dropdown/", response_model=schema.FacilityDropdownResponse)
def read_all_facilities_for_dropdown(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # check_forbidden_roles(db, current_user)
    facilities_data = facilityController.get_all_facilities_for_dropdown(db=db)
    return facilities_data

@router.get("/all-active-for-dropdown/", response_model=schema.FacilityDropdownResponse)
def read_all_facilities_for_dropdown(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # check_forbidden_roles(db, current_user)
    facilities_data = facilityController.get_all_active_facilities_for_dropdown(db=db)
    return facilities_data