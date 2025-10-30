from fastapi import (
    APIRouter, Depends, HTTPException, Query,
    Form, File, UploadFile, Request
)
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..database import get_db

from ..controller import bookingController, usersController, fileController

from ..models import rolesModel, userAccessModel

from ..schemas import bookingSchema, usersSchema 

router = APIRouter(
    prefix="/booking",
    tags=["Booking Management"],
    responses={404: {"description": "Not found"}},
)

# [MODIFIED] Helper baru buat ngecek SEMUA role management (SA, ADM, PIC)
def check_management_access(db: Session, user: usersSchema.User):
    user_access_roles = db.query(rolesModel.Role.vcode).join(
        userAccessModel.UserAccess, rolesModel.Role.nid == userAccessModel.UserAccess.nid_role
    ).filter(
        userAccessModel.UserAccess.nid_user == user.nid, 
        userAccessModel.UserAccess.nstatus == 1
    ).all()
    user_roles = {role[0] for role in user_access_roles}
    
    if "ADM" not in user_roles and "SA" not in user_roles and "PIC" not in user_roles:
        raise HTTPException(status_code=403, detail="Not authorized. Management access (SA/ADM/PIC) required.")
    return user_roles # Kita return set of roles-nya

# Helper lama, tetep dipake buat yg khusus SA/ADM
def check_admin_or_sa(db: Session, user: usersSchema.User):
    user_access_roles = db.query(rolesModel.Role.vcode).join(
        userAccessModel.UserAccess, rolesModel.Role.nid == userAccessModel.UserAccess.nid_role
    ).filter(
        userAccessModel.UserAccess.nid_user == user.nid, 
        userAccessModel.UserAccess.nstatus == 1
    ).all()
    user_roles = {role[0] for role in user_access_roles}
    
    if "ADM" not in user_roles and "SA" not in user_roles:
        raise HTTPException(status_code=403, detail="Not authorized. Admin or Superadmin required.")
    return True

# 1. CREATE BOOKING (User)
@router.post("/", response_model=bookingSchema.BookingSchema, status_code=201)
async def create_booking_api(
    request: Request,
    nid_lab_facility: int = Form(...),
    dstart: datetime = Form(...),
    dend: datetime = Form(...),
    vactivity: str = Form(...),
    proposal_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    if proposal_file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File proposal harus berformat PDF.")
    return await bookingController.create_booking(
        db=db, current_user=current_user, request=request,
        nid_lab_facility=nid_lab_facility, dstart=dstart, dend=dend,
        vactivity=vactivity, proposal_file=proposal_file
    )

# 2. GET ALL BOOKINGS (Admin/SA/PIC)
@router.get("/", response_model=bookingSchema.BookingResponse)
def read_all_bookings_api(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=30),
    vsearch: str = Query(default=""),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # [MODIFIED] Pake helper baru
    user_roles = check_management_access(db, current_user)
    
    return bookingController.get_all_bookings(
        db=db, 
        current_user=current_user, # [MODIFIED] Kirim user & roles-nya
        user_roles=user_roles,
        skip=skip, 
        limit=limit, 
        vsearch=vsearch
    )

# 3. GET MY BOOKINGS (User)
@router.get("/my-bookings", response_model=bookingSchema.BookingResponse)
def read_my_bookings_api(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=30),
    vsearch: str = Query(default=""),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    return bookingController.get_all_bookings_by_user(
        db=db, current_user=current_user, skip=skip, 
        limit=limit, vsearch=vsearch
    )
    
# 4. GET BOOKING BY ID (Owner or Admin/SA/PIC)
@router.get("/{booking_id}", response_model=bookingSchema.BookingSchema)
def read_booking_by_id_api(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    try:
        booking_data = bookingController.get_booking_by_id(db=db, booking_id=booking_id)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail="Booking not found")
        raise e
        
    is_owner = booking_data.nid_user == current_user.nid
    if is_owner:
        return booking_data

    try:
        user_roles = check_management_access(db, current_user)
    except HTTPException:
        raise HTTPException(status_code=403, detail="Not authorized to view this booking")

    # [MODIFIED] Cek scope di API layer
    booked_lab_id = booking_data.lab_facility.nid_lab
    is_scoped = bookingController.check_booking_lab_scope(
        db=db,
        current_user=current_user,
        user_roles=user_roles,
        booking_lab_id=booked_lab_id
    )
    
    if not is_scoped:
         raise HTTPException(status_code=403, detail="Not authorized. Anda hanya bisa melihat booking di Lab yang Anda kelola.")

    return booking_data 

# 5. APPROVE BOOKING (Admin/SA/PIC)
@router.post("/{booking_id}/approve", response_model=bookingSchema.BookingSchema)
async def approve_booking_api(
    request: Request,
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_management_access(db, current_user)
    return await bookingController.update_booking(
        db=db, booking_id=booking_id, current_user=current_user,
        request=request, nstatus=1, doc_images=[], doc_article=None
    )

# 6. REJECT BOOKING (Admin/SA/PIC)
@router.post("/{booking_id}/reject", response_model=bookingSchema.BookingSchema)
async def reject_booking_api(
    request: Request,
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_management_access(db, current_user)
    return await bookingController.update_booking(
        db=db, booking_id=booking_id, current_user=current_user,
        request=request, nstatus=0, doc_images=[], doc_article=None
    )

# 7. UPDATE BOOKING (User upload docs)
@router.put("/{booking_id}", response_model=bookingSchema.BookingSchema)
async def update_booking_api(
    request: Request,
    booking_id: int,
    nstatus: Optional[int] = Form(None),
    doc_images: List[UploadFile] = File([]),
    doc_article: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # [MODIFIED] Endpoint ini dikunci HANYA untuk upload file
    if nstatus is not None:
        raise HTTPException(status_code=400, detail="Ganti status harus via endpoint /approve or /reject.")

    allowed_image_types = ["image/jpeg", "image/png"]
    has_doc_images = doc_images and len(doc_images) > 0 and doc_images[0].filename
    has_doc_article = doc_article and doc_article.filename
    if has_doc_images:
        if len(doc_images) < 2:
            raise HTTPException(status_code=400, detail="Harus mengupload minimal 2 file gambar dokumentasi.")
        for img in doc_images:
            if img.content_type not in allowed_image_types:
                raise HTTPException(status_code=400, detail=f"File gambar {img.filename} harus berformat JPG atau PNG.")
    if has_doc_article and doc_article.content_type != "application/pdf":
         raise HTTPException(status_code=400, detail="File artikel dokumentasi harus berformat PDF.")
    
    return await bookingController.update_booking(
        db=db, booking_id=booking_id, current_user=current_user,
        request=request, nstatus=nstatus, doc_images=doc_images,
        doc_article=doc_article
    )

# 8. DELETE BOOKING (Admin/SA/PIC)
@router.delete("/{booking_id}", response_model=dict)
def delete_booking_api(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # [MODIFIED] Pake helper baru
    user_roles = check_management_access(db, current_user)
    return bookingController.delete_booking(
        db=db, 
        booking_id=booking_id, 
        current_user=current_user,
        user_roles=user_roles # [MODIFIED] Kirim roles
    )

# 9. TRIGGER OVERDUE BOOKINGS (Admin/Cron)
@router.post("/trigger-overdue", response_model=dict)
def trigger_overdue_api(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # [MODIFIED] Endpoint ini tetep pake helper lama (SA/ADM only)
    check_admin_or_sa(db, current_user)
    return bookingController.trigger_update_overdue_bookings(db=db)