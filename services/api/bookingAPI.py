from fastapi import (
    APIRouter, Depends, HTTPException, Query,
    Form, File, UploadFile, Request, status, BackgroundTasks, Header
)
from sqlalchemy.orm import Session
from typing import List, Optional, Set
from datetime import datetime

from ..database import get_db
from utils import email_service

# --- IMPORT UDAH DI-UPDATE ---
from ..controller import bookingController, usersController, fileController, auditLogController
from ..models import rolesModel, userAccessModel
from ..schemas import bookingSchema, usersSchema
# -----------------------------

import calendar

from datetime import datetime
import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def to_wib(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return JAKARTA_TZ.localize(dt) if dt.tzinfo is None else dt.astimezone(JAKARTA_TZ)

router = APIRouter(
    prefix="/booking",
    tags=["Booking Management"],
    responses={404: {"description": "Not found"}},
)

# --- (Fungsi helper check_* access tetep ada) ---

def check_sa_only(db: Session, user: usersSchema.User):
    user_access_roles = db.query(rolesModel.Role.vcode).join(
        userAccessModel.UserAccess, rolesModel.Role.nid == userAccessModel.UserAccess.nid_role
    ).filter(
        userAccessModel.UserAccess.nid_user == user.nid,
        userAccessModel.UserAccess.nstatus == 1
    ).all()
    user_roles = {role[0] for role in user_access_roles}
    
    if "SA" not in user_roles:
        raise HTTPException(status_code=403, detail="Not authorized. Superadmin access required.")
    return True

def check_admin_only(db: Session, user: usersSchema.User):
    user_access_roles = db.query(rolesModel.Role.vcode).join(
        userAccessModel.UserAccess, rolesModel.Role.nid == userAccessModel.UserAccess.nid_role
    ).filter(
        userAccessModel.UserAccess.nid_user == user.nid,
        userAccessModel.UserAccess.nstatus == 1
    ).all()
    user_roles = {role[0] for role in user_access_roles}
    
    if "ADM" not in user_roles:
        raise HTTPException(status_code=403, detail="Not authorized. Admin access required.")
    return True

def check_management_access(db: Session, user: usersSchema.User) -> Set[str]:
    user_access_roles = db.query(rolesModel.Role.vcode).join(
        userAccessModel.UserAccess, rolesModel.Role.nid == userAccessModel.UserAccess.nid_role
    ).filter(
        userAccessModel.UserAccess.nid_user == user.nid,
        userAccessModel.UserAccess.nstatus == 1
    ).all()
    user_roles = {role[0] for role in user_access_roles}
    
    if "ADM" not in user_roles and "SA" not in user_roles and "PIC" not in user_roles:
        raise HTTPException(status_code=403, detail="Not authorized. Management access (SA/ADM/PIC) required.")
    return user_roles

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

def check_sa_adm_pic(db: Session, user: usersSchema.User):
    """
    Memeriksa apakah user adalah SA, ADM, atau PIC.
    """
    user_access_roles = db.query(rolesModel.Role.vcode).join(
        userAccessModel.UserAccess, rolesModel.Role.nid == userAccessModel.UserAccess.nid_role
    ).filter(
        userAccessModel.UserAccess.nid_user == user.nid,
        userAccessModel.UserAccess.nstatus == 1
    ).all()
    
    user_roles = {role[0] for role in user_access_roles} # Ambil vcode
    
    allowed_roles = {"SA", "ADM", "PIC"}
    
    # Cek apakah ada irisan antara role user dan role yang diizinkan
    if not user_roles.intersection(allowed_roles):
        print(f"[AUTH] Gagal: User {user.vemail} (Roles: {user_roles}) mencoba akses endpoint SA/ADM/PIC.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya Superadmin, Admin, atau PIC yang dapat melakukan aksi ini."
        )
    
    # Jika lolos, user punya salah satu role tersebut
    print(f"[AUTH] Sukses: User {user.vemail} (Roles: {user_roles}) diizinkan.")

# -----------------------------------------------
# --- ENDPOINT DENGAN AUDIT LOG ---
# -----------------------------------------------

# 1. CREATE BOOKING (User)
@router.post("/", response_model=bookingSchema.BookingSchema, status_code=201)
async def create_booking_api(
    request: Request,
    background_tasks: BackgroundTasks,
    nid_lab: int = Form(...),
    nid_facility: int = Form(...),
    dstart: datetime = Form(...),
    dend: datetime = Form(...),
    vactivity: str = Form(...),
    proposal_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    if proposal_file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File proposal harus berformat PDF.")
    
    # 1) Create booking dulu
    new_booking = await bookingController.create_booking(
        db=db,
        current_user=current_user,
        request=request,
        dstart=dstart,
        dend=dend,
        nid_lab=nid_lab,
        nid_facility=nid_facility,
        vactivity=vactivity,
        proposal_file=proposal_file,
    )

    # 2) Ambil snapshot data booking SESUDAH create untuk jafter (pakai schema)
    jafter = bookingSchema.BookingSchema.model_validate(new_booking).model_dump(mode="json")

    # 3) Background task notifikasi ke admin
    background_tasks.add_task(
        bookingController.notify_new_booking_to_admins,
        booking_id=new_booking.nid,
        request_base_url=str(request.base_url),
    )

    # 4) Background task audit log
    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="CREATE",
        target_model="Booking",
        target_identifier=new_booking.vcode,
        jbefore=None,
        jafter=jafter,
        ip=request.client.host,
        user_agent=request.headers.get("user-agent"),
    )

    return new_booking

# 5. APPROVE BOOKING (Admin/SA/PIC)
@router.post("/{booking_id}/approve", response_model=bookingSchema.BookingSchema)
def approve_booking_api(
    booking_id: int,
    request: Request, # <-- Tambah Request
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    user_roles = check_management_access(db, current_user)
    
    # --- AMBIL DATA SEBELUM UPDATE ---
    try:
        db_booking_before = bookingController.get_booking_by_id(db=db, booking_id=booking_id)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail="Booking not found for logging")
        raise e
    jbefore = bookingSchema.BookingSchema.model_validate(db_booking_before).model_dump(mode='json')
    # ---------------------------------
    
    updated_booking = bookingController.update_booking_status(
        db=db,
        booking_id=booking_id,
        new_status=1, # Approve
        current_user=current_user,
        user_roles=user_roles
    )
    
    # --- AMBIL DATA SESUDAH UPDATE ---
    jafter = bookingSchema.BookingSchema.model_validate(updated_booking).model_dump(mode='json')
    # ----------------------------------
    
    background_tasks.add_task(
        bookingController.notify_user_of_status_update,
        booking_id=updated_booking.nid,
        new_status=1,
        reviewer_nid=current_user.nid
    )
    
    # --- LOG ACTIVITY (BACKGROUND) ---
    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="UPDATE (APPROVE)",
        target_model="Booking",
        target_identifier=updated_booking.vcode,
        jbefore=jbefore,
        jafter=jafter,
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    # ---------------------------------
    
    return updated_booking

# 6. REJECT BOOKING (Admin/SA/PIC)
@router.post("/{booking_id}/reject", response_model=bookingSchema.BookingSchema)
def reject_booking_api(
    booking_id: int,
    request: Request, # <-- Tambah Request
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    user_roles = check_management_access(db, current_user)
    
    # --- AMBIL DATA SEBELUM UPDATE ---
    try:
        db_booking_before = bookingController.get_booking_by_id(db=db, booking_id=booking_id)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail="Booking not found for logging")
        raise e
    jbefore = bookingSchema.BookingSchema.model_validate(db_booking_before).model_dump(mode='json')
    # ---------------------------------
    
    updated_booking = bookingController.update_booking_status(
        db=db,
        booking_id=booking_id,
        new_status=0, # Reject
        current_user=current_user,
        user_roles=user_roles
    )
    
    # --- AMBIL DATA SESUDAH UPDATE ---
    jafter = bookingSchema.BookingSchema.model_validate(updated_booking).model_dump(mode='json')
    # ----------------------------------
    
    background_tasks.add_task(
        bookingController.notify_user_of_status_update,
        booking_id=updated_booking.nid,
        new_status=0,
        reviewer_nid=current_user.nid
    )
    
    # --- LOG ACTIVITY (BACKGROUND) ---
    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="UPDATE (REJECT)",
        target_model="Booking",
        target_identifier=updated_booking.vcode,
        jbefore=jbefore,
        jafter=jafter,
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    # ---------------------------------
    
    return updated_booking

# 7. UPLOAD DOCUMENTATION (User)
@router.post("/{booking_id}/upload-documentation", response_model=bookingSchema.BookingSchema, status_code=status.HTTP_200_OK)
async def upload_documentation_api(
    request: Request,
    booking_id: int,
    background_tasks: BackgroundTasks, # <-- Tambah BackgroundTasks
    doc_images: List[UploadFile] = File(...),
    doc_article: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    allowed_image_types = ["image/jpeg", "image/png"]
    has_doc_images = doc_images and len(doc_images) > 0 and doc_images[0].filename
    has_doc_article = doc_article and doc_article.filename

    if not has_doc_images:
        raise HTTPException(status_code=400, detail="File gambar dokumentasi wajib diupload.")
        
    if len(doc_images) < 2:
        raise HTTPException(status_code=400, detail="Harus mengupload minimal 2 file gambar dokumentasi.")
    
    for img in doc_images:
        if img.content_type not in allowed_image_types:
            raise HTTPException(status_code=400, detail=f"File gambar {img.filename} harus berformat JPG atau PNG.")
            
    if has_doc_article and doc_article.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="File artikel dokumentasi harus berformat PDF.")
    
    # --- AMBIL DATA SEBELUM UPDATE ---
    try:
        db_booking_before = bookingController.get_booking_by_id(db=db, booking_id=booking_id)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail="Booking not found for logging")
        raise e
    jbefore = bookingSchema.BookingSchema.model_validate(db_booking_before).model_dump(mode='json')
    # ---------------------------------
    
    updated_booking = await bookingController.upload_booking_documentation(
        db=db,
        booking_id=booking_id,
        current_user=current_user,
        request=request,
        doc_images=doc_images,
        doc_article=doc_article
    )
    
    # --- AMBIL DATA SESUDAH UPDATE ---
    jafter = bookingSchema.BookingSchema.model_validate(updated_booking).model_dump(mode='json')
    # ----------------------------------
    
    # --- LOG ACTIVITY (BACKGROUND) ---
    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="UPDATE (UPLOAD DOCUMENTATION)",
        target_model="Booking",
        target_identifier=updated_booking.vcode,
        jbefore=jbefore,
        jafter=jafter,
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    # ---------------------------------
    
    return updated_booking

# 8. DELETE BOOKING (Admin/SA/PIC)
@router.delete("/{booking_id}", response_model=dict)
def delete_booking_api(
    booking_id: int,
    request: Request, # <-- Tambah Request
    background_tasks: BackgroundTasks, # <-- Tambah BackgroundTasks
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    user_roles = check_management_access(db, current_user)
    
    # --- AMBIL DATA SEBELUM DELETE ---
    try:
        db_booking_before = bookingController.get_booking_by_id(db=db, booking_id=booking_id)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail="Booking not found for logging")
        raise e
    jbefore = bookingSchema.BookingSchema.model_validate(db_booking_before).model_dump(mode='json')
    # ---------------------------------
    
    deleted_booking = bookingController.delete_booking(
        db=db,
        booking_id=booking_id,
        current_user=current_user,
        user_roles=user_roles
    )
    
    # --- AMBIL DATA SESUDAH DELETE ---
    jafter = bookingSchema.BookingSchema.model_validate(deleted_booking).model_dump(mode='json')
    # ----------------------------------
    
    # --- LOG ACTIVITY (BACKGROUND) ---
    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="DELETE", 
        target_model="Booking",
        target_identifier=db_booking_before.vcode, 
        jbefore=jbefore,
        jafter=jafter,
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    # ---------------------------------
    
    return {"detail": "Booking successfully deleted (soft delete)"}

# 12. CANCEL BOOKING (Owner)
@router.post("/{booking_id}/cancel", response_model=bookingSchema.BookingSchema)
async def cancel_booking_api(
    booking_id: int,
    request: Request, # <-- Tambah Request
    background_tasks: BackgroundTasks, # <-- Tambah BackgroundTasks
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # --- AMBIL DATA SEBELUM UPDATE ---
    try:
        db_booking_before = bookingController.get_booking_by_id(db=db, booking_id=booking_id)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail="Booking not found for logging")
        raise e
    jbefore = bookingSchema.BookingSchema.model_validate(db_booking_before).model_dump(mode='json')
    # ---------------------------------
    
    updated_booking = await bookingController.cancel_booking_by_owner(
        db=db,
        booking_id=booking_id,
        current_user=current_user
    )
    
    # --- AMBIL DATA SESUDAH UPDATE ---
    jafter = bookingSchema.BookingSchema.model_validate(updated_booking).model_dump(mode='json')
    # ----------------------------------
    
    # --- LOG ACTIVITY (BACKGROUND) ---
    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="UPDATE (CANCEL)", 
        target_model="Booking",
        target_identifier=updated_booking.vcode,
        jbefore=jbefore,
        jafter=jafter,
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    # ---------------------------------
    
    return updated_booking


# -----------------------------------------------
# --- ENDPOINT TANPA AUDIT LOG (READ-ONLY / SYSTEM) ---
# -----------------------------------------------

# 2. GET ALL BOOKINGS (Admin/SA/PIC)
@router.get("/", response_model=bookingSchema.BookingResponse)
def read_all_bookings_api(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    vsearch: str = Query(default=""),
    status: Optional[int] = None,
    dateStart: Optional[datetime] = None,
    dateEnd: Optional[datetime] = None,
    nidLab: Optional[int] = None, 
    nidFacility: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    user_roles = check_management_access(db, current_user)
    
    return bookingController.get_all_bookings(
        db=db,
        current_user=current_user,
        user_roles=user_roles,
        skip=skip,
        limit=limit,
        vsearch=vsearch,
        nstatus=status,
        nid_lab=nidLab,
        nid_facility=nidFacility,
        dstart=to_wib(dateStart),
        dend=to_wib(dateEnd)
    )

@router.get("/by-month", response_model=List[bookingSchema.BookingSchema])
def read_all_bookings_by_month_api(
    month: int = Query(..., description="Filter by month (1-12).", ge=1, le=12),
    year: int = Query(..., description="Filter by year (e.g., 2025).", ge=2020),
    vsearch: str = Query(default=""),
    status: Optional[int] = None,
    nidLab: Optional[int] = None, 
    nidFacility: Optional[int] = None,
    x_chatbot_secret: Optional[str] = Header(None, alias="X-Chatbot-Secret"),
    db: Session = Depends(get_db),
    current_user: Optional[usersSchema.User] = Depends(usersController.get_current_active_user_optional)
):
    # --- LOGIC BYPASS AUTH UNTUK CHATBOT ---
    if x_chatbot_secret == "umnfti2025gacor":
        # Bypass: Anggap sebagai Superadmin (SA) agar bisa lihat semua data
        user_roles = {"SA"}
        # current_user bisa None, controller harus handle ini (get_managed_lab_ids aman utk SA)
    else:
        # Normal Flow: Wajib login
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )
        user_roles = check_management_access(db, current_user)
    # ---------------------------------------
    
    try:
        _, num_days = calendar.monthrange(year, month)
        dstart_calc = JAKARTA_TZ.localize(datetime(year, month, 1, 0, 0, 0))
        dend_calc = JAKARTA_TZ.localize(datetime(year, month, num_days, 23, 59, 59))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month or year value.")

    # Panggil controller BARU
    return bookingController.get_all_bookings_no_pagination(
        db=db,
        current_user=current_user, # Bisa None jika bypass
        user_roles=user_roles,
        vsearch=vsearch,
        nstatus=status,
        nid_lab=nidLab,
        nid_facility=nidFacility,
        dstart=dstart_calc,
        dend=dend_calc
    )

# 3. GET MY BOOKINGS (User)
@router.get("/my-bookings", response_model=bookingSchema.BookingResponse)
def read_my_bookings_api(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=30),
    vsearch: str = Query(default=""),
    status: Optional[int] = None,
    dateStart: Optional[datetime] = None,
    dateEnd: Optional[datetime] = None,
    nidLab: Optional[int] = None, 
    nidFacility: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    return bookingController.get_all_bookings_by_user(
        db=db,
        current_user=current_user,
        skip=skip,
        limit=limit,
        vsearch=vsearch,
        nstatus=status,
        nid_lab=nidLab,
        nid_facility=nidFacility,
        dstart=to_wib(dateStart),
        dend=to_wib(dateEnd)
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

# 9. TRIGGER OVERDUE BOOKINGS (Admin/Cron)
@router.post("/trigger-overdue", response_model=dict)
def trigger_overdue_api(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_admin_or_sa(db, current_user)
    return bookingController.trigger_update_overdue_bookings(db=db)


# 10. TRIGGER GLOBAL PENDING REMINDER (SA -> All Admins + All PICs)
@router.post("/trigger-global-reminder", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
def trigger_global_pending_reminder_api(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # Cuma Superadmin yang bisa trigger global
    check_sa_only(db, current_user) 
    
    background_tasks.add_task(
        bookingController.trigger_global_pending_reminders, # <-- Fungsi GLOBAL
        request_base_url=str(request.base_url)
    )
    
    return {"message": "Tugas pengingat (reminder) global ke semua Admin/PIC telah dimulai."}


# 11. TRIGGER SCOPED PENDING REMINDER (Admin -> PICs in their Dept)
@router.post("/trigger-pic-reminder", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
def trigger_scoped_pic_reminder_api(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # Cuma Admin yang bisa trigger scoped
    check_admin_only(db, current_user) 
    
    background_tasks.add_task(
        bookingController.trigger_scoped_pending_reminders_to_pics, # <-- Fungsi SCOPED
        admin_user_nid=current_user.nid, # <-- Kirim NID Admin-nya
        request_base_url=str(request.base_url)
    )
    
    return {"message": "Tugas pengingat (reminder) ke PIC di bawah departemen Anda telah dimulai."}

@router.post("/trigger-documentation-reminder", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
def trigger_documentation_reminder_api(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # Cek apakah user adalah SA, ADM, atau PIC
    check_sa_adm_pic(db, current_user) 
    
    background_tasks.add_task(
        bookingController.trigger_documentation_reminders, # <-- Fungsi baru kita
        db=db, # Wajib pass db
        current_user=current_user, # Wajib pass user
        request_base_url=str(request.base_url)
    )
    
    return {"message": "Tugas pengingat (reminder) dokumentasi ke user telah dimulai."}

@router.post("/remind-documentation/{booking_code}", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
def trigger_single_documentation_reminder_api(
    booking_code: str, # Ambil dari URL
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # Pake checker yang udah ada buat mastiin yg akses SA/ADM/PIC
    check_sa_adm_pic(db, current_user) 
    
    # Panggil controller baru kita
    return bookingController.trigger_single_documentation_reminder(
        db=db,
        current_user=current_user,
        booking_code=booking_code,
        background_tasks=background_tasks
    )
    
@router.get("/stats/dashboard", response_model=bookingSchema.DashboardStatsResponse)
def get_dashboard_stats_api(
    filter: str = Query('monthly', regex="^(daily|weekly|monthly|yearly|all_time)$"),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    user_roles = check_management_access(db, current_user)
    return bookingController.get_dashboard_stats(
        db=db,
        current_user=current_user,
        user_roles=user_roles,
        filter_type=filter
    )

@router.get("/stats/pending-count", response_model=dict)
def get_pending_count_api(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # Cek akses manajemen (SA/ADM/PIC)
    user_roles = check_management_access(db, current_user)
    
    # Panggil controller baru
    return bookingController.get_pending_booking_count(
        db=db, 
        current_user=current_user, 
        user_roles=user_roles
    )

@router.get("/stats/waiting-doc-count", response_model=dict)
def get_waiting_doc_count_api(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # Cek akses manajemen (SA/ADM/PIC)
    user_roles = check_management_access(db, current_user)
    
    # Panggil controller baru
    return bookingController.get_waiting_doc_booking_count(
        db=db, 
        current_user=current_user, 
        user_roles=user_roles
    )

@router.get("/stats/cancel-count", response_model=dict)
def get_cancel_booking_count_api(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # Cek akses manajemen (SA/ADM/PIC)
    user_roles = check_management_access(db, current_user)
    
    # Panggil controller baru
    return bookingController.get_cancel_booking_count(
        db=db, 
        current_user=current_user, 
        user_roles=user_roles
    )

@router.get("/stats/oldest-waiting-doc", response_model=List[bookingSchema.BookingSchema])
def get_oldest_waiting_doc_bookings_api(
    limit: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # Cek akses manajemen (SA/ADM/PIC)
    user_roles = check_management_access(db, current_user)
    
    return bookingController.get_oldest_waiting_doc_bookings(
        db=db,
        current_user=current_user,
        user_roles=user_roles,
        limit=limit
    )

@router.get("/stats/utilization", response_model=List[dict])
def get_lab_utilization_stats_api(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # Cek akses manajemen (SA/ADM/PIC)
    check_management_access(db, current_user)
    
    return bookingController.get_lab_utilization_stats(db=db)

@router.post("/maintenance", response_model=dict)
def set_booking_maintenance_api(
    request: Request,
    background_tasks: BackgroundTasks,
    nid_lab: int = Form(...),
    nid_facility: Optional[int] = Form(None),
    dstart: datetime = Form(...),
    dend: datetime = Form(...),
    vactivity: str = Form(...),
    force: bool = Form(...),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    user_roles = check_admin_or_sa(db, current_user)

    result = bookingController.set_booking_maintenance(
        nid_lab=nid_lab,
        nid_facility=nid_facility,
        vactivity=vactivity,
        dstart=dstart,
        dend=dend,
        force=force,
        db=db,
        current_user=current_user
    )

    # --- LOG ACTIVITY (BACKGROUND) ---
    # Ambil data booking yang baru dibuat dari result
    booking_data = result.get("booking")
    
    if booking_data:
        # Karena ini create baru, jbefore = None
        jafter = booking_data 
        
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="CREATE (MAINTENANCE)",
            target_model="Booking",
            target_identifier=booking_data.get("vcode"),
            jbefore=None,
            jafter=jafter,
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
    # ---------------------------------

    # --- EMAIL NOTIFICATION (BACKGROUND) ---
    cancelled_bookings = result.get("cancelled_bookings", [])
    if cancelled_bookings:
        print(f"[Maintenance API] Triggering cancellation emails for {len(cancelled_bookings)} bookings.")
        for item in cancelled_bookings:
            # Item is now a dict: {'type': ..., 'booking': ..., 'original_code': ...}
            cb = item.get('booking')
            c_type = item.get('type', 'full')
            orig_code = item.get('original_code')
            
            rem_schedule = item.get('remaining_schedule', [])

            # Pastikan data user dan lab ada
            if cb and cb.user and cb.lab_facility and cb.lab_facility.lab:
                background_tasks.add_task(
                    email_service.send_maintenance_cancellation_email,
                    recipient_email=cb.user.vemail,
                    user_name=cb.user.vname,
                    booking_code=cb.vcode,
                    lab_name=cb.lab_facility.lab.vname,
                    maintenance_reason=vactivity,
                    maintenance_start=dstart,
                    maintenance_end=dend,
                    cancellation_type=c_type,
                    original_code=orig_code,
                    remaining_schedule=rem_schedule,
                    conflict_start=cb.dstart,
                    conflict_end=cb.dend
                )
    
    # Remove raw objects before returning response (to avoid serialization error if any)
    if "cancelled_bookings" in result:
        del result["cancelled_bookings"]
    # ---------------------------------------

    return result


# -----------------------------------------------
# --- PUBLIC ENDPOINTS (NO AUTH) ---
# -----------------------------------------------

@router.get("/public/by-lab/{lab_vcode}", response_model=List[bookingSchema.BookingPublicSchema])
def get_public_bookings_by_lab_api(
    lab_vcode: str,
    month: int = Query(..., description="Filter by month (1-12).", ge=1, le=12),
    year: int = Query(..., description="Filter by year (e.g., 2025).", ge=2020),
    nid_facility: Optional[int] = Query(None, description="Filter by facility ID"),
    db: Session = Depends(get_db),
):
    """
    Get approved/done bookings for a specific lab (public access, no auth required).
    Returns simplified booking data for calendar display.
    Only shows: Approved (1), WaitingForDoc (4), Done (5) bookings.
    """
    try:
        _, num_days = calendar.monthrange(year, month)
        dstart = JAKARTA_TZ.localize(datetime(year, month, 1, 0, 0, 0))
        dend = JAKARTA_TZ.localize(datetime(year, month, num_days, 23, 59, 59))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month or year value.")
    
    return bookingController.get_public_bookings_by_lab(
        db=db,
        lab_vcode=lab_vcode,
        dstart=dstart,
        dend=dend,
        nid_facility=nid_facility
    )
