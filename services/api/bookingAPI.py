from fastapi import (
    APIRouter, Depends, HTTPException, Query,
    Form, File, UploadFile, Request, status, BackgroundTasks
)
from sqlalchemy.orm import Session
from typing import List, Optional, Set
from datetime import datetime

from ..database import get_db

from ..controller import bookingController, usersController, fileController

from ..models import rolesModel, userAccessModel

from ..schemas import bookingSchema, usersSchema


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

# 1. CREATE BOOKING (User)
@router.post("/", response_model=bookingSchema.BookingSchema, status_code=201)
async def create_booking_api(
    request: Request,
    background_tasks: BackgroundTasks,
    # nid_lab_facility: int = Form(...),
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
    new_booking = await bookingController.create_booking(
        db=db, current_user=current_user, request=request,
        # nid_lab_facility=nid_lab_facility, 
        dstart=dstart, dend=dend, nid_lab=nid_lab, nid_facility=nid_facility,
        vactivity=vactivity, proposal_file=proposal_file
    )

    background_tasks.add_task(
        bookingController.notify_new_booking_to_admins, 
        booking_id=new_booking.nid,
        request_base_url=str(request.base_url)
    )
    # ---------------------------------

    return new_booking # API langsung balik, user nggak nunggu email

# 2. GET ALL BOOKINGS (Admin/SA/PIC)
@router.get("/", response_model=bookingSchema.BookingResponse)
def read_all_bookings_api(
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
def approve_booking_api(
    booking_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    user_roles = check_management_access(db, current_user)
    
    updated_booking = bookingController.update_booking_status(
        db=db,
        booking_id=booking_id,
        new_status=1, # Approve
        current_user=current_user,
        user_roles=user_roles
    )
    
    background_tasks.add_task(
        bookingController.notify_user_of_status_update,
        booking_id=updated_booking.nid,
        new_status=1,
        reviewer_nid=current_user.nid
    )
    
    return updated_booking

# 6. REJECT BOOKING (Admin/SA/PIC)
@router.post("/{booking_id}/reject", response_model=bookingSchema.BookingSchema)
def reject_booking_api(
    booking_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    user_roles = check_management_access(db, current_user)
    
    updated_booking = bookingController.update_booking_status(
        db=db,
        booking_id=booking_id,
        new_status=0, # Reject
        current_user=current_user,
        user_roles=user_roles
    )
    
    background_tasks.add_task(
        bookingController.notify_user_of_status_update,
        booking_id=updated_booking.nid,
        new_status=0,
        reviewer_nid=current_user.nid
    )
    
    return updated_booking

# 7. UPLOAD DOCUMENTATION (User)
@router.post("/{booking_id}/upload-documentation", response_model=bookingSchema.BookingSchema, status_code=status.HTTP_200_OK)
async def upload_documentation_api(
    request: Request,
    booking_id: int,
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
    
    return await bookingController.upload_booking_documentation(
        db=db,
        booking_id=booking_id,
        current_user=current_user,
        request=request,
        doc_images=doc_images,
        doc_article=doc_article
    )

# 8. DELETE BOOKING (Admin/SA/PIC)
@router.delete("/{booking_id}", response_model=dict)
def delete_booking_api(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    user_roles = check_management_access(db, current_user)
    return bookingController.delete_booking(
        db=db,
        booking_id=booking_id,
        current_user=current_user,
        user_roles=user_roles
    )

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