from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

# Import database dependency
from ..database import get_db

# Import controllers (logika bisnis)
from ..controller import bookingController, usersController

# Import models (buat cek role)
from ..models import rolesModel, userAccessModel

# Import schemas (request body & response model)
# [FIX] Kita butuh usersSchema buat type hint dependency
from ..schemas import bookingSchema, usersSchema 

router = APIRouter(
    prefix="/booking",
    tags=["Booking Management"], # Nama grup di /docs Swagger
    responses={404: {"description": "Not found"}},
)

# --- Helper Cek Role ---
def check_admin_or_sa(db: Session, user: usersSchema.User): # Hint pake usersSchema.User
    """
    Cek apakah user yg login adalah ADM atau SA.
    Kalo bukan, lempar error 403 Forbidden.
    """
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

# --- ENDPOINT API ---

# 1. CREATE BOOKING (User)
@router.post(
    "/", 
    response_model=bookingSchema.BookingSchema, 
    status_code=201 # 201 Created
)
def create_booking_api(
    booking_data: bookingSchema.BookingCreate,
    db: Session = Depends(get_db),
    # [FIX] Ganti nama fungsinya
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Endpoint untuk user membuat booking baru.
    Status default akan jadi (2) Pending.
    """
    return bookingController.create_booking(
        db=db, 
        booking_data=booking_data, 
        current_user=current_user
    )

# 2. GET ALL BOOKINGS (Admin/SA)
@router.get(
    "/", 
    response_model=dict # Return: {"data": [...], "total": ...}
)
def read_all_bookings_api(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=30),
    vsearch: str = Query(default=""),
    db: Session = Depends(get_db),
    # [FIX] Ganti nama fungsinya
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    [ADMIN/SA] Endpoint untuk mengambil SEMUA booking (dengan pagination & search).
    """
    check_admin_or_sa(db, current_user)
    
    return bookingController.get_all_bookings(
        db=db, 
        skip=skip, 
        limit=limit, 
        vsearch=vsearch
    )

# 3. GET MY BOOKINGS (User)
@router.get(
    "/my-bookings",
    response_model=dict # Return: {"data": [...], "total": ...}
)
def read_my_bookings_api(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=30),
    vsearch: str = Query(default=""),
    db: Session = Depends(get_db),
    # [FIX] Ganti nama fungsinya
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Endpoint untuk user melihat history booking-nya sendiri.
    """
    return bookingController.get_all_bookings_by_user(
        db=db, 
        current_user=current_user, 
        skip=skip, 
        limit=limit, 
        vsearch=vsearch
    )
    
# 4. GET BOOKING BY ID (Owner or Admin/SA)
@router.get(
    "/{booking_id}",
    response_model=bookingSchema.BookingSchema
)
def read_booking_by_id_api(
    booking_id: int,
    db: Session = Depends(get_db),
    # [FIX] Ganti nama fungsinya
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Endpoint untuk mengambil detail 1 booking.
    Hanya bisa diakses oleh Admin/SA atau user yg membuat booking.
    """
    try:
        booking_data_dict = bookingController.get_booking_by_id(db=db, booking_id=booking_id)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail="Booking not found")
        raise e
        
    # --- Security Check di API Layer ---
    user_access_roles = db.query(rolesModel.Role.vcode).join(
        userAccessModel.UserAccess, rolesModel.Role.nid == userAccessModel.UserAccess.nid_role
    ).filter(
        userAccessModel.UserAccess.nid_user == current_user.nid, 
        userAccessModel.UserAccess.nstatus == 1
    ).all()
    user_roles = {role[0] for role in user_access_roles}
    is_admin_or_sa = "ADM" in user_roles or "SA" in user_roles
    
    is_owner = booking_data_dict["nid_user"] == current_user.nid

    if not is_admin_or_sa and not is_owner:
        raise HTTPException(status_code=403, detail="Not authorized to view this booking")
        
    return booking_data_dict 

# 5. UPDATE BOOKING (Status or Documentation)
@router.put(
    "/{booking_id}",
    response_model=bookingSchema.BookingSchema
)
def update_booking_api(
    booking_id: int,
    update_data: bookingSchema.BookingUpdate,
    db: Session = Depends(get_db),
    # [FIX] Ganti nama fungsinya
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Endpoint untuk update booking.
    (Semua permission logic SUDAH di-handle di controller).
    """
    return bookingController.update_booking(
        db=db, 
        booking_id=booking_id, 
        update_data=update_data, 
        current_user=current_user
    )

# 6. DELETE BOOKING (Admin/SA)
@router.delete(
    "/{booking_id}",
    response_model=dict
)
def delete_booking_api(
    booking_id: int,
    db: Session = Depends(get_db),
    # [FIX] Ganti nama fungsinya
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    [ADMIN/SA] Endpoint untuk soft-delete booking (set nstatus = 0).
    (Permission logic SUDAH di-handle di controller).
    """
    return bookingController.delete_booking(
        db=db, 
        booking_id=booking_id, 
        current_user=current_user
    )

# 7. TRIGGER OVERDUE BOOKINGS (Admin/Cron)
@router.post(
    "/trigger-overdue",
    response_model=dict
)
def trigger_overdue_api(
    db: Session = Depends(get_db),
    # [FIX] Ganti nama fungsinya
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    [ADMIN/CRON] Endpoint untuk mentrigger update status
    dari (1) Approved -> (4) Waiting for Documentation
    jika tanggal 'dend' sudah lewat.
    """
    check_admin_or_sa(db, current_user)
    
    return bookingController.trigger_update_overdue_bookings(db=db)