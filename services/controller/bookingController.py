from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import func, or_, desc, and_
from fastapi import HTTPException, Request, UploadFile, BackgroundTasks
import uuid
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Set
from collections import defaultdict

from ..database import SessionLocal 
from utils import email_service
from ..models.bookingModel import Booking
from ..models.bookingFilesModel import BookingFile
from ..models.labFacilityModel import LabFacility
from ..models import usersModel, rolesModel, labModel, facilityModel, filesModel
from ..models.userAccessModel import UserAccess
from ..models.departmentLabModel import DepartmentLab
from ..models.labFacilityModel import LabFacility

from ..schemas.bookingSchema import BookingSchema
from ..schemas.bookingFilesSchema import BookingFileCreate
from ..schemas.usersSchema import User

from . import fileController

import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")
def now_wib():
    return datetime.now(JAKARTA_TZ)

# --- HELPERS ---

def to_wib(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        return JAKARTA_TZ.localize(dt)
    return dt.astimezone(JAKARTA_TZ)

def generate_unique_booking_code(db: Session) -> str:
    while True:
        # Menghasilkan 8 karakter hex (e.g., 1A2B3C4D)
        unique_part = secrets.token_hex(4).upper()
        new_code = f"BOOKING-{unique_part}"
        
        # Cek ke database
        exists = db.query(Booking).filter(Booking.vcode == new_code).first()
        if not exists:
            # Kalo belum ada, kita pake kode ini
            return new_code

def get_managed_lab_ids(db: Session, current_user: usersModel.User, user_roles: Set[str]) -> List[int]:
    if 'VSTR' in user_roles:
        return []

    if 'SA' in user_roles:
        # Superadmin sees ALL labs (active & inactive)
        all_labs = db.query(labModel.Lab.nid).all()
        return [lab.nid for lab in all_labs]

    user_access_records = db.query(UserAccess.nid_lab).filter(
        UserAccess.nid_user == current_user.nid,
        UserAccess.nid_lab != None,
        UserAccess.nstatus == 1
    ).distinct().all()

    return [record.nid_lab for record in user_access_records]

def check_booking_lab_scope(
    db: Session,
    current_user: usersModel.User,
    user_roles: Set[str],
    booking_lab_id: int
) -> bool:
    has_access = db.query(UserAccess).filter(
        UserAccess.nid_user == current_user.nid,
        UserAccess.nid_lab == booking_lab_id,
        UserAccess.nstatus == 1
    ).first()

    return has_access is not None

def check_booking_availability(
    db: Session,
    lab_facility_id: int,
    start_date: datetime,
    end_date: datetime,
    exclude_booking_id: Optional[int] = None
):
    booked_statuses = [1]
    query = db.query(Booking).filter(
        Booking.nid_lab_facility == lab_facility_id,
        Booking.nstatus.in_(booked_statuses),
        Booking.dstart < end_date,
        Booking.dend > start_date
    )
    if exclude_booking_id:
        query = query.filter(Booking.nid != exclude_booking_id)
    return query.count() == 0

def replace_booking_files_by_type(db: Session, booking_id: int, file_type: str, new_file_ids: List[int], current_user: usersModel.User):
    db.query(BookingFile).filter(
        BookingFile.nid_booking == booking_id,
        BookingFile.vtype == file_type,
        BookingFile.nstatus == 1
    ).update({"nstatus": 0, "vmodified_by": current_user.vcode})
    
    new_files = []
    if new_file_ids:
        for file_id in new_file_ids:
            new_files.append(
                BookingFile(
                    vcode=str(uuid.uuid4()), nid_booking=booking_id,
                    nid_file=file_id, vtype=file_type,
                    vcreated_by=current_user.vcode, dsort_at=now_wib()
                )
            )
        db.add_all(new_files)
    return len(new_files) > 0

def upsert_booking_file(db: Session, booking_id: int, file_type: str, new_file_id: Optional[int], current_user: usersModel.User):
    if new_file_id is None: return False
    
    existing_file = db.query(BookingFile).filter(
        BookingFile.nid_booking == booking_id,
        BookingFile.vtype == file_type,
        BookingFile.nstatus == 1
    ).with_for_update().first()
    
    if existing_file:
        if existing_file.nid_file != new_file_id:
            existing_file.nid_file = new_file_id
            existing_file.vmodified_by = current_user.vcode
            return True
        return False
    else:
        db_file = BookingFile(
            vcode=str(uuid.uuid4()), nid_booking=booking_id,
            nid_file=new_file_id, vtype=file_type,
            vcreated_by=current_user.vcode, dsort_at=now_wib()
        )
        db.add(db_file)
        return True

def trigger_update_overdue_bookings(db: Session):
    now = now_wib()
    overdue_bookings = db.query(Booking).filter(
        Booking.nstatus == 1,
        Booking.dend < now
    ).with_for_update().all()
    
    if not overdue_bookings:
        return {"updated_count": 0, "detail": "No overdue bookings found"}
    
    updated_ids = []
    for booking in overdue_bookings:
        booking.nstatus = 4
        booking.vmodified_by = "SYSTEM_SCHEDULER"
        updated_ids.append(booking.nid)
        
    try:
        db.commit()
        return {
            "updated_count": len(updated_ids),
            "detail": f"Successfully updated {len(updated_ids)} bookings to 'Waiting For Documentation'.",
            "updated_ids": updated_ids
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update overdue bookings: {str(e)}")

# --- FUNGSI CRUD ---

def get_all_bookings(
    db: Session,
    current_user: usersModel.User,
    user_roles: Set[str],
    skip: int = 0,
    limit: int = 10,
    vsearch: str = "",
    dstart: datetime | None = None,
    dend: datetime | None = None,
    nstatus: int | None = None,
    nid_lab: int | None = None, 
    nid_facility: int | None = None,
):
    query = db.query(Booking).options(
        joinedload(Booking.user),
        joinedload(Booking.lab_facility).joinedload(LabFacility.lab),
        joinedload(Booking.lab_facility).joinedload(LabFacility.facility),
        selectinload(Booking.booking_files).joinedload(BookingFile.file)
    )

    managed_lab_ids = get_managed_lab_ids(db, current_user, user_roles)
    
    if not managed_lab_ids:
         return {"data": [], "total": 0}
    
    query = query.join(
        LabFacility, Booking.nid_lab_facility == LabFacility.nid
    ).filter(
        LabFacility.nid_lab.in_(managed_lab_ids)
    )

    if vsearch:
        query = query.join(Booking.user).join(labModel.Lab, LabFacility.nid_lab == labModel.Lab.nid)
        query = query.filter(
            or_(
                Booking.vcode.ilike(f"%{vsearch}%"),
                Booking.vactivity.ilike(f"%{vsearch}%"),
                usersModel.User.vname.ilike(f"%{vsearch}%"),
                labModel.Lab.vname.ilike(f"%{vsearch}%"),
            )
        )

    if nstatus is not None:
        query = query.filter(Booking.nstatus == nstatus)
    if nid_facility is not None:
        query = query.filter(LabFacility.nid_facility == nid_facility)
    if nid_lab is not None:
        query = query.filter(LabFacility.nid_lab == nid_lab)
    if dstart is not None and dend is not None:
        query = query.filter(
            func.date(Booking.dstart) <= dend,
            func.date(Booking.dend) >= dstart
        )
    elif dstart is not None:
        query = query.filter(func.date(Booking.dend) >= dstart)
    elif dend is not None:
        query = query.filter(func.date(Booking.dstart) <= dend)

    total = query.count()
    results = query.order_by(Booking.dsort_at.desc()).offset(skip).limit(limit).all()

    return {"data": results, "total": total}


def get_all_bookings_by_user(
    db: Session,
    current_user: usersModel.User,
    skip: int = 0,
    limit: int = 10,
    vsearch: str = "",
    dstart: datetime | None = None,
    dend: datetime | None = None,
    nstatus: int | None = None,
    nid_lab: int | None = None, 
    nid_facility: int | None = None,
):
    query = db.query(Booking).filter(Booking.nid_user == current_user.nid)
    
    # [KEEP] Biarin aja outerjoin manual ini buat filter
    query = query.outerjoin(
        LabFacility, Booking.nid_lab_facility == LabFacility.nid
    ).outerjoin(
        labModel.Lab, LabFacility.nid_lab == labModel.Lab.nid
    ).outerjoin(
        facilityModel.Facility, LabFacility.nid_facility == facilityModel.Facility.nid
    )
    
    # [UBAH] Ganti blok options lu jadi PAKE JOINEDLOAD
    query = query.options(
        # Ini akan bikin JOIN duplikat, tapi harusnya datanya ke-load
        joinedload(Booking.lab_facility).joinedload(LabFacility.lab), 
        joinedload(Booking.lab_facility).joinedload(LabFacility.facility), 
        
        # Ini udah bener
        selectinload(Booking.booking_files).joinedload(BookingFile.file)
    )
    
    if vsearch:
         query = query.filter(
            or_(
                Booking.vcode.ilike(f"%{vsearch}%"), 
                Booking.vactivity.ilike(f"%{vsearch}%"),
                labModel.Lab.vname.ilike(f"%{vsearch}%"),
                facilityModel.Facility.vname.ilike(f"%{vsearch}%")
            )
        )
    
    if nstatus is not None:
        query = query.filter(Booking.nstatus == nstatus)
    if nid_facility is not None:
        query = query.filter(LabFacility.nid_facility == nid_facility)
    if nid_lab is not None:
        query = query.filter(LabFacility.nid_lab == nid_lab)
    if dstart is not None and dend is not None:
        query = query.filter(
            func.date(Booking.dstart) <= dend,
            func.date(Booking.dend) >= dstart
        )
    elif dstart is not None:
        query = query.filter(func.date(Booking.dend) >= dstart)
    elif dend is not None:
        query = query.filter(func.date(Booking.dstart) <= dend)
         
    total = query.count()
    results = query.order_by(Booking.dsort_at.desc()).offset(skip).limit(limit).all()
    return {"data": results, "total": total}

def get_booking_by_id(db: Session, booking_id: int):
    db_booking = db.query(Booking).options(
        joinedload(Booking.user),
        joinedload(Booking.lab_facility).joinedload(LabFacility.lab),
        joinedload(Booking.lab_facility).joinedload(LabFacility.facility),
        selectinload(Booking.booking_files).joinedload(BookingFile.file)
    ).filter(Booking.nid == booking_id).first()
    
    if not db_booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return db_booking

async def create_booking(db: Session, current_user: usersModel.User, request: Request, 
                        #  nid_lab_facility: int, 
                        nid_lab: int,
                        nid_facility: int,
                         dstart: datetime, dend: datetime, vactivity: str, proposal_file: UploadFile):
    if dend <= dstart:
        raise HTTPException(status_code=400, detail="End date must be after start date")

    # [NEW] Validation: Batas booking harian jam 17:00
    current_time = now_wib()
    if current_time.hour >= 17:
        # Konversi dstart ke WIB untuk perbandingan tanggal
        booking_start_wib = to_wib(dstart)
        if booking_start_wib.date() <= current_time.date():
             raise HTTPException(
                 status_code=400, 
                 detail="Booking untuk hari ini sudah ditutup (batas jam 17:00). Silakan lakukan booking untuk besok atau hari berikutnya."
             )
    
    # [NEW] Validation: Tidak bisa booking hari Minggu
    booking_start_wib = to_wib(dstart)
    if booking_start_wib.weekday() == 6: # 0=Monday, 6=Sunday
        raise HTTPException(
            status_code=400,
            detail="Layanan tutup pada hari Minggu. Silakan pilih hari lain."
        )
    
    lab_facility = db.query(LabFacility).filter(
        LabFacility.nid_lab == nid_lab,
        LabFacility.nid_facility == nid_facility,
        LabFacility.nstatus == 1
    ).first()
    
    if not lab_facility:
        raise HTTPException(status_code=404, detail="Kombinasi Lab dan Fasilitas tidak ditemukan atau tidak aktif")
    
    nid_lab_facility = lab_facility.nid
        
    is_available = check_booking_availability(
        db, lab_facility_id=nid_lab_facility,
        start_date=dstart, end_date=dend
    )
    if not is_available:
        raise HTTPException(status_code=409, detail="Booking conflict: The selected date is not available")
    
    db_proposal_file = None
    try:
        db_proposal_file = await fileController.save_file(
            db=db, file=proposal_file, category="bookingDocs",
            current_user=current_user, request=request, is_public=False, prefix="PROP"
        )
        if not db_proposal_file:
             raise HTTPException(status_code=500, detail="Gagal menyimpan file proposal.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memproses file: {str(e)}")
        
    try:
        new_booking_code = generate_unique_booking_code(db)
        db_booking = Booking(
            vcode=new_booking_code, nid_lab_facility=nid_lab_facility,
            nid_user=current_user.nid, dstart=to_wib(dstart), dend=to_wib(dend),
            vactivity=vactivity, nstatus=2, vcreated_by=current_user.vcode,
            dsort_at=now_wib()
        )
        db.add(db_booking)
        db.flush()
        
        upsert_booking_file(
            db=db, booking_id=db_booking.nid, file_type="proposal",
            new_file_id=db_proposal_file.nid, current_user=current_user
        )
        
        db.commit()
        db.refresh(db_booking)
        return get_booking_by_id(db, db_booking.nid)
    except Exception as e:
        db.rollback()
        try:
            fileController.permanently_delete_file_record(db, db_proposal_file.nid)
        except Exception as del_e:
            print(f"CRITICAL: GAGAL ROLLBACK FILE FISIK {db_proposal_file.vpath} SETELAH DB ERROR: {del_e}")
        raise HTTPException(status_code=500, detail=f"Failed to create booking database record: {str(e)}")


# --- [REFACTOR] FUNGSI UPDATE DIPISAH ---

def update_booking_status(
    db: Session,
    booking_id: int,
    new_status: int,
    current_user: usersModel.User,
    user_roles: Set[str]
):
    is_management = 'ADM' in user_roles or 'SA' in user_roles or 'PIC' in user_roles
    
    if not is_management:
        raise HTTPException(status_code=403, detail="Hanya Admin, PIC, atau Superadmin yang bisa ganti status.")

    db_booking = db.query(Booking).options(
        joinedload(Booking.lab_facility)
    ).filter(
        Booking.nid == booking_id
    ).with_for_update().first()

    if not db_booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if db_booking.nstatus == 0:
        raise HTTPException(status_code=404, detail="Booking already deleted")

    booked_lab_id = db_booking.lab_facility.nid_lab
    old_status = db_booking.nstatus

    if new_status == old_status:
        return get_booking_by_id(db, db_booking.nid)
    
    modified = False

    if new_status == 1: # Approve
        if old_status != 2:
            raise HTTPException(status_code=409, detail=f"Booking hanya bisa di-approve dari status Pending (2).")
        
        is_available = check_booking_availability(
            db, lab_facility_id=db_booking.nid_lab_facility,
            start_date=db_booking.dstart, end_date=db_booking.dend,
            exclude_booking_id=db_booking.nid
        )
        if not is_available:
            raise HTTPException(status_code=409, detail="Maaf, jadwal yang dipilih tidak tersedia karena telah dipesan oleh pengguna lain.")

        is_scoped = check_booking_lab_scope(db, current_user, user_roles, booked_lab_id)
        if not is_scoped:
            raise HTTPException(status_code=403, detail="Otorisasi gagal: Anda hanya bisa approve booking di Lab yang Anda kelola.")

        db_booking.nstatus = new_status
        db_booking.dreviewed_at = now_wib()
        db_booking.vreviewed_by = current_user.vcode
        modified = True
    
    elif new_status == 0: # Reject
        if old_status != 2:
            raise HTTPException(status_code=409, detail=f"Booking hanya bisa di-reject dari status Pending (2).")
        
        is_scoped = check_booking_lab_scope(db, current_user, user_roles, booked_lab_id)
        if not is_scoped:
            raise HTTPException(status_code=403, detail="Otorisasi gagal: Anda hanya bisa reject booking di Lab yang Anda kelola.")
        
        db_booking.nstatus = new_status
        db_booking.dreviewed_at = now_wib() # Catat waktu reject
        db_booking.vreviewed_by = current_user.vcode # Catat siapa yg reject
        modified = True

    elif new_status == 3: # Cancel
        is_owner = db_booking.nid_user == current_user.nid
        if not is_owner and not is_management:
            raise HTTPException(status_code=403, detail="Hanya owner atau admin/PIC/SA yang bisa cancel.")
        if old_status not in [1, 2]:
             raise HTTPException(status_code=409, detail="Booking can only be canceled if Pending or Approved")
        
        db_booking.nstatus = new_status
        db_booking.dcanceled_at = now_wib()
        
        modified = True

    elif new_status in [4, 5]: # Manual Override
         if 'SA' not in user_roles and 'ADM' not in user_roles:
             raise HTTPException(status_code=403, detail="Hanya Admin atau Superadmin yang bisa ganti status manual ke 4 atau 5.")
        
         db_booking.nstatus = new_status
        #  if old_status == 1:
        #     db_booking.dreviewed_at = None
        #     db_booking.vreviewed_by = None
         modified = True
    
    else:
         raise HTTPException(status_code=400, detail=f"Invalid status change: {old_status} to {new_status}")

    if modified:
        try:
            db_booking.vmodified_by = current_user.vcode
            db_booking.dsort_at = now_wib()
            db.commit()
            db.refresh(db_booking)
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Gagal menyimpan update status booking: {str(e)}")

    return get_booking_by_id(db, db_booking.nid)


async def upload_booking_documentation(
    db: Session,
    booking_id: int,
    current_user: usersModel.User,
    request: Request,
    doc_images: List[UploadFile],
    doc_article: Optional[UploadFile]
):
    db_booking = db.query(Booking).options(
        joinedload(Booking.lab_facility)
    ).filter(
        Booking.nid == booking_id
    ).with_for_update().first()

    if not db_booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if db_booking.nstatus == 0:
        raise HTTPException(status_code=404, detail="Booking already deleted")

    if db_booking.nstatus != 4:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot upload documentation. Booking status is '{db_booking.nstatus}', must be 'Waiting For Documentation (4)'."
        )
    
    if db_booking.nid_user != current_user.nid:
            raise HTTPException(status_code=403, detail="Hanya user pembuat booking yang bisa upload dokumentasi.")

    modified = False
    files_uploaded_in_this_request = False
    list_of_new_file_ids_to_rollback = []

    has_doc_images = doc_images and len(doc_images) > 0 and doc_images[0].filename
    has_doc_article = doc_article and doc_article.filename

    try:
        if has_doc_images:
            new_image_ids: List[int] = []
            for img_file in doc_images:
                db_img_file = await fileController.save_file(
                    db=db, file=img_file, category="bookingDocs",
                    current_user=current_user, request=request, is_public=False, prefix="DOC"
                )
                new_image_ids.append(db_img_file.nid)
                list_of_new_file_ids_to_rollback.append(db_img_file.nid)
            if replace_booking_files_by_type(db, booking_id, "documentation_image", new_image_ids, current_user):
                modified = True
                files_uploaded_in_this_request = True
        
        if has_doc_article:
            db_article_file = await fileController.save_file(
                db=db, file=doc_article, category="bookingDocs",
                current_user=current_user, request=request, is_public=False, prefix="OUT"
            )
            list_of_new_file_ids_to_rollback.append(db_article_file.nid)
            if upsert_booking_file(db, booking_id, "documentation_article", db_article_file.nid, current_user):
                modified = True
                files_uploaded_in_this_request = True
        
        # --- [INI DIA FIXNYA] ---
        if files_uploaded_in_this_request:
            db.flush() # Paksa kirim data file ke DB (tapi blm commit)
            
    except Exception as e:
        db.rollback() # Rollback kalo ada error pas nyimpen file
        for file_id in list_of_new_file_ids_to_rollback:
            try: fileController.permanently_delete_file_record(db, file_id)
            except Exception: pass
        raise HTTPException(status_code=500, detail=f"Gagal memproses file dokumentasi: {str(e)}")

    # Sekarang query di bawah ini bakal dapet data yg bener
    if db_booking.nstatus == 4 and files_uploaded_in_this_request:
        image_count = db.query(BookingFile).filter(
            BookingFile.nid_booking == db_booking.nid,
            BookingFile.vtype == "documentation_image",
            BookingFile.nstatus == 1
        ).count()
        article_file = db.query(BookingFile).filter(
            BookingFile.nid_booking == db_booking.nid,
            BookingFile.vtype == "documentation_article",
            BookingFile.nstatus == 1
        ).first()
        
        if image_count >= 2 and article_file is not None:
            db_booking.nstatus = 5
            modified = True

    if modified:
        try:
            db_booking.vmodified_by = current_user.vcode
            db_booking.dsort_at = now_wib()
            db.commit() # Commit file DAN status barunya (kalo ada)
            db.refresh(db_booking)
        except Exception as e:
            db.rollback()
            for file_id in list_of_new_file_ids_to_rollback:
                try: fileController.permanently_delete_file_record(db, file_id)
                except Exception: pass
            raise HTTPException(status_code=500, detail=f"Gagal menyimpan update booking: {str(e)}")

    return get_booking_by_id(db, db_booking.nid)


# --- FUNGSI DELETE ---

def delete_booking(
    db: Session,
    booking_id: int,
    current_user: usersModel.User,
    user_roles: Set[str]
):
    db_booking = db.query(Booking).options(
        joinedload(Booking.lab_facility)
    ).filter(
        Booking.nid == booking_id
    ).with_for_update().first()
    
    if not db_booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    booked_lab_id = db_booking.lab_facility.nid_lab
    is_scoped = check_booking_lab_scope(db, current_user, user_roles, booked_lab_id)
    if not is_scoped:
        raise HTTPException(status_code=403, detail="Otorisasi gagal: Anda hanya bisa delete booking di Lab yang Anda kelola.")

    db_booking.nstatus = 0
    db_booking.dsort_at = now_wib()
    db_booking.vmodified_by = current_user.vcode
    db.commit()

    return {"detail": "Booking successfully deleted (soft delete)"}

def trigger_single_documentation_reminder(
    db: Session, 
    current_user: User, 
    booking_code: str,
    background_tasks: BackgroundTasks
):
    """
    Memicu reminder dokumentasi untuk satu booking spesifik (by vcode).
    Hanya bisa dilakukan oleh SA/ADM/PIC yang punya scope ke lab tsb.
    """
    # 1. Ambil Role user (buat cek scope)
    user_access_roles = db.query(rolesModel.Role.vcode).join(
       UserAccess, rolesModel.Role.nid == UserAccess.nid_role
    ).filter(
        UserAccess.nid_user == current_user.nid,
        UserAccess.nstatus == 1
    ).all()
    user_roles = {role[0] for role in user_access_roles}
    
    # 2. Cari Booking berdasarkan VCODE-nya
    db_booking = db.query(Booking).options(
        joinedload(Booking.lab_facility) # Cukup load ini buat cek scope
    ).filter(Booking.vcode == booking_code).first()

    # 3. Validasi: Booking Gak Ketemu
    if not db_booking:
        raise HTTPException(status_code=404, detail=f"Booking with code {booking_code} not found")

    # 4. Validasi: Cek Scope
    if not db_booking.lab_facility or not db_booking.lab_facility.nid_lab:
         raise HTTPException(status_code=500, detail="Booking data is corrupted (missing lab facility link)")
    
    booked_lab_id = db_booking.lab_facility.nid_lab
    # Pake helper check_booking_lab_scope
    is_scoped = check_booking_lab_scope(db, current_user, user_roles, booked_lab_id)
    
    if not is_scoped:
        raise HTTPException(status_code=403, detail="Not authorized. Anda hanya bisa me-remind booking di Lab yang Anda kelola.")

    # 5. Validasi: Status Booking
    if db_booking.nstatus != 4: #
        raise HTTPException(status_code=409, detail=f"Booking {booking_code} is not 'Waiting For Documentation' (status 4).")
    
    # 6. Kalo lolos semua, lempar ke Background Task
    background_tasks.add_task(task_send_single_doc_reminder, db_booking.nid) # Kirim NID-nya

    # 7. Kasih response sukses
    return {"message": f"Reminder for booking {booking_code} has been successfully queued."}

async def notify_new_booking_to_admins(booking_id: int, request_base_url: str):
    """
    [BACKGROUND TASK] Mengirim notifikasi email booking baru 
    ke PIC Lab dan Admin Department terkait.
    """
    print(f"[Notify] Mulai proses notifikasi untuk booking ID: {booking_id}")
    db: Session = SessionLocal()
    try:
        # 1. Ambil data booking lengkap
        db_booking = db.query(Booking).options(
            joinedload(Booking.user),
            joinedload(Booking.lab_facility).joinedload(LabFacility.lab)
        ).filter(Booking.nid == booking_id).first()

        if not db_booking:
            print(f"[Notify] Error: Booking ID {booking_id} tidak ditemukan.")
            return

        booked_lab = db_booking.lab_facility.lab
        booked_user = db_booking.user
        booked_lab_id = booked_lab.nid

        # 2. Cari Department ID dari Lab
        db_dept_lab = db.query(DepartmentLab).filter(
            DepartmentLab.nid_lab == booked_lab_id,
            DepartmentLab.nstatus == 1
        ).first()
        booked_dept_id = db_dept_lab.nid_department if db_dept_lab else None

        recipient_emails = set()

        # 3. Cari email semua PIC Lab ini
        pic_emails_query = db.query(usersModel.User.vemail).join(
            UserAccess, usersModel.User.nid == UserAccess.nid_user
        ).join(
            rolesModel.Role, UserAccess.nid_role == rolesModel.Role.nid
        ).filter(
            rolesModel.Role.vcode == 'PIC',
            UserAccess.nid_lab == booked_lab_id,
            UserAccess.nstatus == 1,
            usersModel.User.nstatus == 1
        )
        for (email,) in pic_emails_query.all():
            recipient_emails.add(email)

        # 4. Cari email semua ADM Department ini (kalo ada)
        if booked_dept_id:
            admin_emails_query = db.query(usersModel.User.vemail).join(
                UserAccess, usersModel.User.nid == UserAccess.nid_user
            ).join(
                rolesModel.Role, UserAccess.nid_role == rolesModel.Role.nid
            ).filter(
                rolesModel.Role.vcode == 'ADM',
                UserAccess.nid_department == booked_dept_id,
                UserAccess.nstatus == 1,
                usersModel.User.nstatus == 1
            )
            for (email,) in admin_emails_query.all():
                recipient_emails.add(email)

        if not recipient_emails:
            print(f"[Notify] Tidak ada penerima (PIC/ADM) ditemukan untuk booking {booking_id}.")
            return

        # 5. Siapkan konten email
        final_recipients = list(recipient_emails)
        subject = f"[Booking Lab Baru] {booked_lab.vname} - {booked_user.vname}"

        # Bikin detail booking
        details_html = f"""
        <p>Halo,</p>
        <p>Ada booking lab baru yang membutuhkan review Anda:</p>
        <ul>
            <li><strong>Pemohon:</strong> {booked_user.vname} ({booked_user.vemail})</li>
            <li><strong>Lab:</strong> {booked_lab.vname}</li>
            <li><strong>Aktivitas:</strong> {db_booking.vactivity}</li>
            <li><strong>Mulai:</strong> {db_booking.dstart.strftime('%Y-%m-%d %H:%M')}</li>
            <li><strong>Selesai:</strong> {db_booking.dend.strftime('%Y-%m-%d %H:%M')}</li>
            <li><strong>Status:</strong> Pending</li>
        </ul>
        <p>Silakan login ke sistem manajemen lab untuk me-review (Approve/Reject) booking ini.</p>
        """

        base_url = email_service.BASE_URL_FRONTEND 
        review_url = f"{base_url}/management/monitoring/booking" 

        html_content = email_service.create_styled_html_body(
                title="Notifikasi Booking Baru",
                main_content=details_html,
                button_text="Review Booking Sekarang",
                button_url=review_url
            )

        email_sukses = await email_service.send_email_async(
                recipients=final_recipients,
                subject=subject,
                html_content=html_content
            )
            
            
        if email_sukses:
            print(f"[Notify] Sukses kirim notifikasi booking {booking_id} ke {len(final_recipients)} penerima.")
        else:
            print(f"[Notify] Gagal kirim email (setelah styling) untuk booking {booking_id}.")

    except Exception as e:
        print(f"[Notify ERROR] Gagal proses notifikasi untuk booking {booking_id}: {str(e)}")
    finally:
        db.close()
        
async def notify_user_of_status_update(booking_id: int, new_status: int, reviewer_nid: int):
    """
    [BACKGROUND TASK] Mengirim notifikasi email ke user 
    setelah booking-nya di-approve atau di-reject.
    """
    print(f"[Notify User] Mulai proses notifikasi status ({new_status}) untuk booking ID: {booking_id}")
    db: Session = SessionLocal()
    try:
        # 1. Ambil data booking lengkap
        db_booking = db.query(Booking).options(
            joinedload(Booking.user),
            joinedload(Booking.lab_facility).joinedload(LabFacility.lab)
        ).filter(Booking.nid == booking_id).first()
        
        if new_status == 1:
            new_status_str = "Disetujui"
        elif new_status == 0:
            new_status_str = "Ditolak"
        
        if db_booking.dreviewed_at is None:
            print(f"[Notify User] WARNING: dreviewed_at masih None untuk booking {booking_id}. Pake waktu sekarang.")
            review_time = now_wib()
        else:
            review_time = db_booking.dreviewed_at

        booked_user = db_booking.user
        booked_lab = db_booking.lab_facility.lab
        
        # Ambil data reviewer
        db_reviewer = db.query(usersModel.User).filter(usersModel.User.nid == reviewer_nid).first()
        reviewer_name = db_reviewer.vname if db_reviewer else "Admin"

        # 3. Kirim email
        await email_service.send_booking_status_email(
            recipient_email=booked_user.vemail,
            user_name=booked_user.vname,
            booking_code=db_booking.vcode,
            lab_name=booked_lab.vname,
            activity=db_booking.vactivity,
            new_status_str=new_status_str,
            reviewer_name=reviewer_name,
            reviewed_at=review_time
        )

    except Exception as e:
        print(f"[Notify User ERROR] Gagal proses notifikasi untuk booking {booking_id}: {str(e)}")
    finally:
        db.close()
        
async def trigger_global_pending_reminders(request_base_url: str):
    """
    [BACKGROUND TASK] Memicu pengiriman email reminder ke 
    semua PIC/Admin yang punya booking 'Pending' (status 2).
    """
    print("[Reminder Job] Mulai menjalankan tugas pengingat booking pending...")
    db: Session = SessionLocal()
    
    # Map untuk mengelompokkan booking per admin/pic
    # Format: { "admin_email@mail.com": {"name": "Nama Admin", "bookings": [booking1, booking2]} }
    reminders_map = defaultdict(lambda: {"name": "Admin/PIC", "bookings": []})
    
    try:
        # 1. Ambil semua booking yang masih 'Pending' (status 2)
        pending_bookings = db.query(Booking).options(
            joinedload(Booking.user),
            joinedload(Booking.lab_facility).joinedload(LabFacility.lab)
        ).filter(Booking.nstatus == 2).order_by(Booking.dcreated_at.asc()).all()

        if not pending_bookings:
            print("[Reminder Job] Tidak ada booking 'Pending'. Tugas selesai.")
            return

        print(f"[Reminder Job] Ditemukan {len(pending_bookings)} booking 'Pending'. Mulai mengelompokkan...")

        # 2. Kelompokkan booking berdasarkan siapa admin/pic-nya
        for booking in pending_bookings:
            booked_lab = booking.lab_facility.lab
            booked_lab_id = booked_lab.nid
            
            db_dept_lab = db.query(DepartmentLab).filter(
                DepartmentLab.nid_lab == booked_lab_id,
                DepartmentLab.nstatus == 1
            ).first()
            booked_dept_id = db_dept_lab.nid_department if db_dept_lab else None

            recipient_users = set() # Pakai set (email, name)

            # 3. Cari PIC Lab (Sama kayak logic notif)
            pic_users_query = db.query(usersModel.User.vemail, usersModel.User.vname).join(
                UserAccess, usersModel.User.nid == UserAccess.nid_user
            ).join(
                rolesModel.Role, UserAccess.nid_role == rolesModel.Role.nid
            ).filter(
                rolesModel.Role.vcode == 'PIC',
                UserAccess.nid_lab == booked_lab_id,
                UserAccess.nstatus == 1,
                usersModel.User.nstatus == 1
            )
            for email, name in pic_users_query.all():
                recipient_users.add((email, name))

            # 4. Cari ADM Department (Sama kayak logic notif)
            if booked_dept_id:
                admin_users_query = db.query(usersModel.User.vemail, usersModel.User.vname).join(
                    UserAccess, usersModel.User.nid == UserAccess.nid_user
                ).join(
                    rolesModel.Role, UserAccess.nid_role == rolesModel.Role.nid
                ).filter(
                    rolesModel.Role.vcode == 'ADM',
                    UserAccess.nid_department == booked_dept_id,
                    UserAccess.nstatus == 1,
                    usersModel.User.nstatus == 1
                )
                for email, name in admin_users_query.all():
                    recipient_users.add((email, name))

            # 5. Masukkan ke map
            for email, name in recipient_users:
                reminders_map[email]["name"] = name
                reminders_map[email]["bookings"].append(booking)

        if not reminders_map:
            print("[Reminder Job] Tidak ada admin/pic yang ter-mapping. Selesai.")
            return
            
        print(f"[Reminder Job] Akan mengirim reminder ke {len(reminders_map)} admin/pic.")

        # 6. Kirim email ke tiap admin/pic
        for admin_email, data in reminders_map.items():
            admin_name = data["name"]
            bookings_list = data["bookings"]
            pending_count = len(bookings_list)
            
            # Buat list HTML <ul>...</ul>
            bookings_html_list = "<ul>"
            for b in bookings_list:
                bookings_html_list += f"""
                <li style="margin-bottom: 10px;">
                    <strong>{b.lab_facility.lab.vname}</strong> - {b.vactivity}
                    <br>
                    <small style="color: #555;">
                        Oleh: {b.user.vname} (Diajukan: {b.dcreated_at.strftime('%Y-%m-%d %H:%M')})
                    </small>
                </li>
                """
            bookings_html_list += "</ul>"
            
            # Kirim email
            await email_service.send_pending_reminder_email(
                recipient_email=admin_email,
                user_name=admin_name,
                pending_count=pending_count,
                bookings_html_list=bookings_html_list
            )

        print("[Reminder Job] Semua email reminder telah di-queue. Tugas selesai.")

    except Exception as e:
        print(f"[Reminder Job ERROR] Gagal total: {str(e)}")
    finally:
        db.close()
        
async def trigger_scoped_pending_reminders_to_pics(admin_user_nid: int, request_base_url: str):
    """
    [BACKGROUND TASK - SCOPED] Memicu pengiriman email reminder ke 
    PIC Lab yang berada di bawah departemen ADMIN yang me-request.
    """
    print(f"[Reminder Job - SCOPED] Admin NID {admin_user_nid} memulai tugas pengingat ke PIC...")
    db: Session = SessionLocal()
    
    reminders_map = defaultdict(lambda: {"name": "PIC", "bookings": []})
    
    try:
        # 1. Cari departemen yang di-manage oleh Admin ini
        managed_dept_ids_query = db.query(UserAccess.nid_department).join(
            rolesModel.Role, UserAccess.nid_role == rolesModel.Role.nid
        ).filter(
            UserAccess.nid_user == admin_user_nid,
            rolesModel.Role.vcode == 'ADM',
            UserAccess.nstatus == 1
        ).distinct()
        
        managed_dept_ids = [d[0] for d in managed_dept_ids_query.all() if d[0] is not None]

        if not managed_dept_ids:
            print(f"[Reminder Job - SCOPED] Admin NID {admin_user_nid} tidak mengelola departemen apapun. Selesai.")
            return

        # 2. Cari lab yang ada di bawah departemen tersebut
        managed_lab_ids_query = db.query(DepartmentLab.nid_lab).filter(
            DepartmentLab.nid_department.in_(managed_dept_ids),
            DepartmentLab.nstatus == 1
        ).distinct()
        
        managed_lab_ids = [l[0] for l in managed_lab_ids_query.all() if l[0] is not None]

        if not managed_lab_ids:
            print(f"[Reminder Job - SCOPED] Tidak ada Lab ditemukan untuk departemen Admin NID {admin_user_nid}. Selesai.")
            return

        # 3. Ambil semua booking 'Pending' (status 2) HANYA UNTUK LAB-LAB TSB
        pending_bookings = db.query(Booking).join(
            LabFacility, Booking.nid_lab_facility == LabFacility.nid
        ).options(
            joinedload(Booking.user),
            joinedload(Booking.lab_facility).joinedload(LabFacility.lab)
        ).filter(
            Booking.nstatus == 2,
            LabFacility.nid_lab.in_(managed_lab_ids)
        ).order_by(Booking.dcreated_at.asc()).all()

        if not pending_bookings:
            print(f"[Reminder Job - SCOPED] Tidak ada booking 'Pending' di lab yang dikelola Admin NID {admin_user_nid}. Selesai.")
            return

        print(f"[Reminder Job - SCOPED] Ditemukan {len(pending_bookings)} booking 'Pending'. Mulai mengelompokkan PIC...")

        # 4. Kelompokkan booking HANYA berdasarkan PIC-nya
        for booking in pending_bookings:
            booked_lab_id = booking.lab_facility.lab.nid
            
            # Cari HANYA PIC Lab
            pic_users_query = db.query(usersModel.User.vemail, usersModel.User.vname).join(
                UserAccess, usersModel.User.nid == UserAccess.nid_user
            ).join(
                rolesModel.Role, UserAccess.nid_role == rolesModel.Role.nid
            ).filter(
                rolesModel.Role.vcode == 'PIC',
                UserAccess.nid_lab == booked_lab_id,
                UserAccess.nstatus == 1,
                usersModel.User.nstatus == 1
            )
            
            for email, name in pic_users_query.all():
                reminders_map[email]["name"] = name
                reminders_map[email]["bookings"].append(booking)

        if not reminders_map:
            print("[Reminder Job - SCOPED] Tidak ada PIC yang ter-mapping. Selesai.")
            return
            
        print(f"[Reminder Job - SCOPED] Akan mengirim reminder ke {len(reminders_map)} PIC.")

        # 5. Kirim email ke tiap PIC (Logic ini sama persis)
        for pic_email, data in reminders_map.items():
            pic_name = data["name"]
            bookings_list = data["bookings"]
            pending_count = len(bookings_list)
            
            bookings_html_list = "<ul>"
            for b in bookings_list:
                bookings_html_list += f"""
                <li style="margin-bottom: 10px;">
                    <strong>{b.lab_facility.lab.vname}</strong> - {b.vactivity}
                    <br><small style='color: #555;'>Oleh: {b.user.vname} (Diajukan: {b.dcreated_at.strftime('%Y-%m-%d %H:%M')})</small>
                </li>
                """
            bookings_html_list += "</ul>"
            
            await email_service.send_pending_reminder_email(
                recipient_email=pic_email,
                user_name=pic_name,
                pending_count=pending_count,
                bookings_html_list=bookings_html_list
            )

        print("[Reminder Job - SCOPED] Semua email reminder untuk PIC telah di-queue. Tugas selesai.")

    except Exception as e:
        print(f"[Reminder Job ERROR - SCOPED] Gagal total: {str(e)}")
    finally:
        db.close()

async def trigger_documentation_reminders(
    db: Session, 
    current_user: User, 
    request_base_url: str
):
    """
    Mengirim email reminder ke USER yang booking-nya berstatus 4 (Waiting For Documentation),
    sesuai dengan scope dari current_user (SA, ADM, atau PIC).
    """
    print(f"[Doc Reminder Job] Dimulai oleh: {current_user.vemail}")
    
    try:
        user_access_tuples = db.query(
            UserAccess,
            rolesModel.Role.vcode  # Ambil vcode langsung dari tabel Role
        ).join(
            rolesModel.Role, UserAccess.nid_role == rolesModel.Role.nid # Join manual
        ).filter(
            UserAccess.nid_user == current_user.nid,
            UserAccess.nstatus == 1
        ).all()
        # Hasilnya adalah list of tuples: [(UserAccessObject1, 'SA'), (UserAccessObject2, 'ADM')]

        if not user_access_tuples:
            print(f"[Doc Reminder Job] Gagal: User {current_user.vemail} tidak punya role aktif.")
            return

        # Pisahkan vcode dan list access
        user_role_codes = {vcode for access, vcode in user_access_tuples}
        print(f"[Doc Reminder Job] Role terdeteksi: {user_role_codes}")
        # --- SELESAI BAGIAN YANG DIGANTI ---


        base_query = db.query(Booking).options(
            joinedload(Booking.user),
            joinedload(Booking.lab_facility).joinedload(LabFacility.lab)
        ).filter(Booking.nstatus == 4)

        bookings_to_remind = []

        if "SA" in user_role_codes:
            print("[Doc Reminder Job] Scope: SA (Global). Mengambil semua booking status 4.")
            bookings_to_remind = base_query.all()
        
        elif "ADM" in user_role_codes:
            # Dapatkan ID Departemen dari tuples
            admin_dept_ids = set()
            for access, vcode in user_access_tuples: # <--- Ganti logic perulangan
                if vcode == "ADM" and access.nid_department:
                    admin_dept_ids.add(access.nid_department)
            
            if not admin_dept_ids:
                print("[Doc Reminder Job] Scope: ADM, tapi tidak ada departemen ter-assign. Selesai.")
                return
            
            print(f"[Doc Reminder Job] Scope: ADM. Departemen: {admin_dept_ids}")
            
            # Query ini sudah benar (tidak bergantung pada relationship UserAccess)
            scoped_query = base_query.join(
                LabFacility, Booking.nid_lab_facility == LabFacility.nid
            ).join(
                labModel.Lab, LabFacility.nid_lab == labModel.Lab.nid
            ).join(
                DepartmentLab, labModel.Lab.nid == DepartmentLab.nid_lab
            ).filter(
                DepartmentLab.nid_department.in_(admin_dept_ids)
            )
            bookings_to_remind = scoped_query.all()

        elif "PIC" in user_role_codes:
            # Dapatkan ID Lab dari tuples
            pic_lab_ids = set()
            for access, vcode in user_access_tuples: # <--- Ganti logic perulangan
                if vcode == "PIC" and access.nid_lab:
                    pic_lab_ids.add(access.nid_lab)

            if not pic_lab_ids:
                print("[Doc Reminder Job] Scope: PIC, tapi tidak ada lab ter-assign. Selesai.")
                return

            print(f"[Doc Reminder Job] Scope: PIC. Lab: {pic_lab_ids}")
            
            # Query ini sudah benar
            scoped_query = base_query.join(
                LabFacility, Booking.nid_lab_facility == LabFacility.nid
            ).filter(
                LabFacility.nid_lab.in_(pic_lab_ids)
            )
            bookings_to_remind = scoped_query.all()
        
        else:
            print(f"[Doc Reminder Job] Gagal: User {current_user.vemail} tidak punya role SA/ADM/PIC.")
            return

        if not bookings_to_remind:
            print("[Doc Reminder Job] Tidak ada booking berstatus 4 yang sesuai scope. Selesai.")
            return

        print(f"[Doc Reminder Job] Ditemukan {len(bookings_to_remind)} booking yang perlu diingatkan.")

        reminders_map = defaultdict(lambda: {"name":     "", "bookings": []})
        
        for b in bookings_to_remind:
            if not b.user:
                continue
            reminders_map[b.user.vemail]["name"] = b.user.vname
            reminders_map[b.user.vemail]["bookings"].append(b)

        if not reminders_map:
            print("[Doc Reminder Job] Tidak ada user valid untuk dikirim email. Selesai.")
            return
            
        print(f"[Doc Reminder Job] Akan mengirim reminder ke {len(reminders_map)} user.")

        for user_email, data in reminders_map.items():
            user_name = data["name"]
            bookings_list = data["bookings"]
            pending_count = len(bookings_list)
            
            bookings_html_list = "<ul>"
            for b in bookings_list:
                lab_name = b.lab_facility.lab.vname if b.lab_facility and b.lab_facility.lab else "Lab tidak diketahui"
                bookings_html_list += f"""
                <li style="margin-bottom: 10px;">
                    <strong>{lab_name}</strong> - {b.vactivity}
                    <br><small style='color: #555;'>Kode Booking: {b.vcode} (Selesai: {b.dend.strftime('%Y-%m-%d')})</small>
                </li>
                """
            bookings_html_list += "</ul>"
            
            await email_service.send_documentation_reminder_email(
                recipient_email=user_email,
                user_name=user_name,
                pending_count=pending_count,
                bookings_html_list=bookings_html_list
            )

        print("[Doc Reminder Job] Semua email reminder dokumentasi telah di-queue.")

    except Exception as e:
        print(f"❌ [Doc Reminder Job] Terjadi error: {e}")
    finally:
        db.close()
        
        
async def task_send_single_doc_reminder(booking_id: int):
    """
    [BACKGROUND TASK] Mengirim email reminder dokumentasi tunggal ke user.
    Mengambil data dari DB berdasarkan ID.
    """
    db: Session = SessionLocal() # Bikin sesi DB baru untuk task
    try:
        # Ambil data lengkap yang dibutuhin buat email
        db_booking = db.query(Booking).options(
            joinedload(Booking.user),
            joinedload(Booking.lab_facility).joinedload(LabFacility.lab)
        ).filter(Booking.nid == booking_id).first()

        if not db_booking:
            print(f"[Single Doc Reminder] Gagal: Booking NID {booking_id} tidak ditemukan.")
            return

        user_to_remind = db_booking.user
        if not user_to_remind:
            print(f"[Single Doc Reminder] Gagal: Booking {db_booking.vcode} (NID: {booking_id}) tidak memiliki data user.")
            return
        
        # Cek ulang status, siapa tau udah di-submit pas task-nya jalan
        if db_booking.nstatus != 4: #
            print(f"[Single Doc Reminder] Dibatalkan: Booking {db_booking.vcode} (NID: {booking_id}) tidak lagi berstatus 4.")
            return

        # Siapin data buat email
        user_email = user_to_remind.vemail
        user_name = user_to_remind.vname
        lab_name = db_booking.lab_facility.lab.vname if db_booking.lab_facility and db_booking.lab_facility.lab else "Lab tidak diketahui"
        
        # Bikin list HTML-nya (isinya cuma 1)
        bookings_html_list = f"""
        <ul>
            <li style="margin-bottom: 10px;">
                <strong>{lab_name}</strong> - {db_booking.vactivity}
                <br><small style='color: #555;'>Kode Booking: {db_booking.vcode} (Selesai: {db_booking.dend.strftime('%Y-%m-%d')})</small>
            </li>
        </ul>
        """
        
        # Panggil service email yang udah ada
        await email_service.send_documentation_reminder_email(
            recipient_email=user_email,
            user_name=user_name,
            pending_count=1,
            bookings_html_list=bookings_html_list
        )
        print(f"[Single Doc Reminder] Sukses mengirim email untuk booking {db_booking.vcode} ke {user_email}.")
    
    except Exception as e:
        print(f"❌ [Single Doc Reminder] Terjadi error untuk booking NID {booking_id}: {e}")
    finally:
        db.close() # Penting: selalu tutup sesi DB
        

def get_pending_booking_count(db: Session, current_user: usersModel.User, user_roles: Set[str]):
    """
    Menghitung jumlah booking yang berstatus 'Pending' (2)
    sesuai dengan scope lab yang dikelola user.
    """
    # Ambil ID lab yang dikelola user ini
    managed_lab_ids = get_managed_lab_ids(db, current_user, user_roles)
    
    if not managed_lab_ids:
        return {"count": 0} # Kalo gak ngelola apa-apa, count-nya 0
    
    # Query count yang di-scope
    count = db.query(Booking.nid).join(
        LabFacility, Booking.nid_lab_facility == LabFacility.nid
    ).filter(
        Booking.nstatus == 2, # 2 = Pending
        LabFacility.nid_lab.in_(managed_lab_ids) # Filter sesuai scope
    ).count()
    
    return {"count": count}

def get_cancel_booking_count(db: Session, current_user: usersModel.User, user_roles: Set[str]):
    """
    Menghitung jumlah booking yang berstatus 'Cancelled' 
    sesuai dengan scope lab yang dikelola user.
    """
    # Ambil ID lab yang dikelola user ini
    managed_lab_ids = get_managed_lab_ids(db, current_user, user_roles)
    
    if not managed_lab_ids:
        return {"count": 0} # Kalo gak ngelola apa-apa, count-nya 0
    
    # Query count yang di-scope
    count = db.query(Booking.nid).join(
        LabFacility, Booking.nid_lab_facility == LabFacility.nid
    ).filter(
        Booking.nstatus == 3, 
        LabFacility.nid_lab.in_(managed_lab_ids) # Filter sesuai scope
    ).count()
    
    return {"count": count}

def get_waiting_doc_booking_count(db: Session, current_user: usersModel.User, user_roles: Set[str]):
    """
    Menghitung jumlah booking yang berstatus 'Waiting For Documentation' (4)
    sesuai dengan scope lab yang dikelola user.
    """
    # Ambil ID lab yang dikelola user ini
    managed_lab_ids = get_managed_lab_ids(db, current_user, user_roles)
    
    if not managed_lab_ids:
        return {"count": 0} # Kalo gak ngelola apa-apa, count-nya 0
    
    # Query count yang di-scope
    count = db.query(Booking.nid).join(
        LabFacility, Booking.nid_lab_facility == LabFacility.nid
    ).filter(
        Booking.nstatus == 4, # 4 = WaitingForDoc
        LabFacility.nid_lab.in_(managed_lab_ids) # Filter sesuai scope
    ).count()
    
    return {"count": count}


async def cancel_booking_by_owner(
    db: Session,
    booking_id: int,
    current_user: usersModel.User
):
    """
    Hanya owner yang bisa cancel booking, 
    jika statusnya Pending (2) atau Approved (1).
    """
    db_booking = db.query(Booking).filter(
        Booking.nid == booking_id
    ).with_for_update().first()

    if not db_booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if db_booking.nstatus == 0:
        raise HTTPException(status_code=404, detail="Booking already deleted")

    # 1. Cek Otorisasi: HARUS owner
    if db_booking.nid_user != current_user.nid:
        raise HTTPException(status_code=403, detail="Only the user who created this booking can cancel it.")
        
    old_status = db_booking.nstatus
    
    # 2. Cek Status: HARUS 1 (Approved) or 2 (Pending)
    if old_status not in [1, 2]:
        if old_status == 3:
            raise HTTPException(status_code=409, detail="Booking is already canceled.")
        elif old_status == 4:
            raise HTTPException(status_code=409, detail="Booking is already waiting for documentation; cannot be canceled.")
        elif old_status == 5:
            raise HTTPException(status_code=409, detail="Booking is already completed; cannot be canceled.")
        elif old_status == 0:
            raise HTTPException(status_code=404, detail="Booking already rejected")
        else:
            raise HTTPException(
                status_code=409, 
                detail=f"Booking cannot be canceled because its status is not Pending or Approved (Current status: {old_status})."
            )
    
    # 3. Kalo lolos, eksekusi
    db_booking.nstatus = 3 # Set Canceled
    db_booking.dcanceled_at = now_wib() # Catet waktunya
    db_booking.vmodified_by = current_user.vcode
    db_booking.dsort_at = now_wib()
    
    try:
        db.commit()
        db.refresh(db_booking)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan update status booking: {str(e)}")

    # Kembalikan data utuh
    return get_booking_by_id(db, db_booking.nid)

from datetime import timedelta

def calculate_date_ranges(filter_type: str):
    now = now_wib()
    
    if filter_type == 'daily':
        # 24 jam terakhir
        start_current = now - timedelta(days=1)
        end_current = now
        # 24 jam sebelumnya
        start_prev = start_current - timedelta(days=1)
        end_prev = start_current
        
    elif filter_type == 'weekly':
        # 7 hari terakhir
        start_current = now - timedelta(days=7)
        end_current = now
        # 7 hari sebelumnya
        start_prev = start_current - timedelta(days=7)
        end_prev = start_current
        
    elif filter_type == 'monthly':
        # 30 hari terakhir
        start_current = now - timedelta(days=30)
        end_current = now
        # 30 hari sebelumnya
        start_prev = start_current - timedelta(days=30)
        end_prev = start_current

    elif filter_type == 'yearly':
        # 1 tahun terakhir (365 hari)
        start_current = now - timedelta(days=365)
        end_current = now
        # 1 tahun sebelumnya
        start_prev = start_current - timedelta(days=365)
        end_prev = start_current

    elif filter_type == 'all_time':
        # All Time (Sejak tahun 2000)
        start_current = datetime(2000, 1, 1, tzinfo=JAKARTA_TZ)
        end_current = now
        # Trend tidak relevan untuk All Time, set prev ke range kosong
        start_prev = start_current
        end_prev = start_current
        
    else: # Default monthly
        start_current = now - timedelta(days=30)
        end_current = now
        start_prev = start_current - timedelta(days=30)
        end_prev = start_current
        
    return start_current, end_current, start_prev, end_prev

def get_dashboard_stats(
    db: Session, 
    current_user: usersModel.User, 
    user_roles: Set[str],
    filter_type: str = 'monthly'
):
    # 1. Scope Check
    managed_lab_ids = get_managed_lab_ids(db, current_user, user_roles)
    if not managed_lab_ids:
        return {
            "pending_count": 0,
            "waiting_doc_count": 0,
            "cancelled_count": 0,
            "total_booking": {
                "count": 0,
                "trend_percentage": 0.0,
                "trend_direction": "flat",
                "previous_count": 0
            }
        }

    # 2. Date Ranges
    start_curr, end_curr, start_prev, end_prev = calculate_date_ranges(filter_type)

    # 3. Base Query Builder
    def count_bookings(status_list: List[int], start_dt, end_dt):
        return db.query(Booking.nid).join(
            LabFacility, Booking.nid_lab_facility == LabFacility.nid
        ).filter(
            Booking.nstatus.in_(status_list),
            LabFacility.nid_lab.in_(managed_lab_ids),
            Booking.dcreated_at >= start_dt,
            Booking.dcreated_at <= end_dt
        ).count()

    # 4. Execute Queries
    
    # TOTAL REQUEST (All Statuses: 0, 1, 2, 3, 4, 5)
    total_req_curr = count_bookings([0, 1, 2, 3, 4, 5], start_curr, end_curr)
    total_req_prev = count_bookings([0, 1, 2, 3, 4, 5], start_prev, end_prev)

    # Breakdown (Current Period)
    pending = count_bookings([2], start_curr, end_curr)
    waiting = count_bookings([4], start_curr, end_curr)
    cancelled = count_bookings([3], start_curr, end_curr)
    approved = count_bookings([1], start_curr, end_curr)
    done = count_bookings([5], start_curr, end_curr)
    rejected = count_bookings([0], start_curr, end_curr)

    # 5. Calculate Trend for Total Request
    if total_req_prev == 0:
        if total_req_curr > 0:
            trend_pct = 100.0
            direction = "up"
        else:
            trend_pct = 0.0
            direction = "flat"
    else:
        diff = total_req_curr - total_req_prev
        trend_pct = (diff / total_req_prev) * 100.0
        if diff > 0:
            direction = "up"
        elif diff < 0:
            direction = "down"
        else:
            direction = "flat"

    return {
        "total_request": {
            "count": total_req_curr,
            "trend_percentage": round(abs(trend_pct), 1),
            "trend_direction": direction,
            "previous_count": total_req_prev
        },
        "pending_count": pending,
        "waiting_doc_count": waiting,
        "cancelled_count": cancelled,
        "approved_count": approved,
        "done_count": done,
        "rejected_count": rejected
    }

def get_all_bookings_no_pagination(
    db: Session,
    current_user: usersModel.User,
    user_roles: Set[str],
    vsearch: str = "",
    dstart: datetime | None = None,
    dend: datetime | None = None,
    nstatus: int | None = None,
    nid_lab: int | None = None, 
    nid_facility: int | None = None,
):
    # --- LOGIC FILTER (COPY-PASTE DARI get_all_bookings) ---
    query = db.query(Booking).options(
        joinedload(Booking.user),
        joinedload(Booking.lab_facility).joinedload(LabFacility.lab),
        joinedload(Booking.lab_facility).joinedload(LabFacility.facility),
        selectinload(Booking.booking_files).joinedload(BookingFile.file)
    )

    managed_lab_ids = get_managed_lab_ids(db, current_user, user_roles)
    
    if not managed_lab_ids:
         return [] # Return list kosong
    
    query = query.join(
        LabFacility, Booking.nid_lab_facility == LabFacility.nid
    ).filter(
        LabFacility.nid_lab.in_(managed_lab_ids)
    )

    if vsearch:
        query = query.join(Booking.user).join(labModel.Lab, LabFacility.nid_lab == labModel.Lab.nid)
        query = query.filter(
            or_(
                Booking.vcode.ilike(f"%{vsearch}%"),
                Booking.vactivity.ilike(f"%{vsearch}%"),
                usersModel.User.vname.ilike(f"%{vsearch}%"),
                labModel.Lab.vname.ilike(f"%{vsearch}%"),
            )
        )

    if nstatus is not None:
        query = query.filter(Booking.nstatus == nstatus)
    if nid_facility is not None:
        query = query.filter(LabFacility.nid_facility == nid_facility)
    if nid_lab is not None:
        query = query.filter(LabFacility.nid_lab == nid_lab)
    
    # Filter tanggal (wajib ada)
    if dstart is not None and dend is not None:
        query = query.filter(
            func.date(Booking.dstart) <= dend,
            func.date(Booking.dend) >= dstart
        )
    elif dstart is not None:
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan update status booking: {str(e)}")

    # Kembalikan data utuh
    return get_booking_by_id(db, db_booking.nid)

from datetime import timedelta

def calculate_date_ranges(filter_type: str):
    now = now_wib()
    
    if filter_type == 'daily':
        # 24 jam terakhir
        start_current = now - timedelta(days=1)
        end_current = now
        # 24 jam sebelumnya
        start_prev = start_current - timedelta(days=1)
        end_prev = start_current
        
    elif filter_type == 'weekly':
        # 7 hari terakhir
        start_current = now - timedelta(days=7)
        end_current = now
        # 7 hari sebelumnya
        start_prev = start_current - timedelta(days=7)
        end_prev = start_current
        
    elif filter_type == 'monthly':
        # 30 hari terakhir
        start_current = now - timedelta(days=30)
        end_current = now
        # 30 hari sebelumnya
        start_prev = start_current - timedelta(days=30)
        end_prev = start_current

    elif filter_type == 'yearly':
        # 1 tahun terakhir (365 hari)
        start_current = now - timedelta(days=365)
        end_current = now
        # 1 tahun sebelumnya
        start_prev = start_current - timedelta(days=365)
        end_prev = start_current

    elif filter_type == 'all_time':
        # All Time (Sejak tahun 2000)
        start_current = datetime(2000, 1, 1, tzinfo=JAKARTA_TZ)
        end_current = now
        # Trend tidak relevan untuk All Time, set prev ke range kosong
        start_prev = start_current
        end_prev = start_current
        
    else: # Default monthly
        start_current = now - timedelta(days=30)
        end_current = now
        start_prev = start_current - timedelta(days=30)
        end_prev = start_current
        
    return start_current, end_current, start_prev, end_prev

def get_dashboard_stats(
    db: Session, 
    current_user: usersModel.User, 
    user_roles: Set[str],
    filter_type: str = 'monthly'
):
    # 1. Scope Check
    managed_lab_ids = get_managed_lab_ids(db, current_user, user_roles)
    if not managed_lab_ids:
        return {
            "pending_count": 0,
            "waiting_doc_count": 0,
            "cancelled_count": 0,
            "total_booking": {
                "count": 0,
                "trend_percentage": 0.0,
                "trend_direction": "flat",
                "previous_count": 0
            }
        }

    # 2. Date Ranges
    start_curr, end_curr, start_prev, end_prev = calculate_date_ranges(filter_type)

    # 3. Base Query Builder
    def count_bookings(status_list: List[int], start_dt, end_dt):
        return db.query(Booking.nid).join(
            LabFacility, Booking.nid_lab_facility == LabFacility.nid
        ).filter(
            Booking.nstatus.in_(status_list),
            LabFacility.nid_lab.in_(managed_lab_ids),
            Booking.dcreated_at >= start_dt,
            Booking.dcreated_at <= end_dt
        ).count()

    # 4. Execute Queries
    
    # TOTAL REQUEST (All Statuses: 0, 1, 2, 3, 4, 5)
    total_req_curr = count_bookings([0, 1, 2, 3, 4, 5], start_curr, end_curr)
    total_req_prev = count_bookings([0, 1, 2, 3, 4, 5], start_prev, end_prev)

    # Breakdown (Current Period)
    pending = count_bookings([2], start_curr, end_curr)
    waiting = count_bookings([4], start_curr, end_curr)
    cancelled = count_bookings([3], start_curr, end_curr)
    approved = count_bookings([1], start_curr, end_curr)
    done = count_bookings([5], start_curr, end_curr)
    rejected = count_bookings([0], start_curr, end_curr)

    # 5. Calculate Trend for Total Request
    if total_req_prev == 0:
        if total_req_curr > 0:
            trend_pct = 100.0
            direction = "up"
        else:
            trend_pct = 0.0
            direction = "flat"
    else:
        diff = total_req_curr - total_req_prev
        trend_pct = (diff / total_req_prev) * 100.0
        if diff > 0:
            direction = "up"
        elif diff < 0:
            direction = "down"
        else:
            direction = "flat"

    return {
        "total_request": {
            "count": total_req_curr,
            "trend_percentage": round(abs(trend_pct), 1),
            "trend_direction": direction,
            "previous_count": total_req_prev
        },
        "pending_count": pending,
        "waiting_doc_count": waiting,
        "cancelled_count": cancelled,
        "approved_count": approved,
        "done_count": done,
        "rejected_count": rejected
    }

def get_all_bookings_no_pagination(
    db: Session,
    current_user: usersModel.User,
    user_roles: Set[str],
    vsearch: str = "",
    dstart: datetime | None = None,
    dend: datetime | None = None,
    nstatus: int | None = None,
    nid_lab: int | None = None, 
    nid_facility: int | None = None,
):
    # --- LOGIC FILTER (COPY-PASTE DARI get_all_bookings) ---
    query = db.query(Booking).options(
        joinedload(Booking.user),
        joinedload(Booking.lab_facility).joinedload(LabFacility.lab),
        joinedload(Booking.lab_facility).joinedload(LabFacility.facility),
        selectinload(Booking.booking_files).joinedload(BookingFile.file)
    )

    managed_lab_ids = get_managed_lab_ids(db, current_user, user_roles)
    
    if not managed_lab_ids:
         return [] # Return list kosong
    
    query = query.join(
        LabFacility, Booking.nid_lab_facility == LabFacility.nid
    ).filter(
        LabFacility.nid_lab.in_(managed_lab_ids)
    )

    if vsearch:
        query = query.join(Booking.user).join(labModel.Lab, LabFacility.nid_lab == labModel.Lab.nid)
        query = query.filter(
            or_(
                Booking.vcode.ilike(f"%{vsearch}%"),
                Booking.vactivity.ilike(f"%{vsearch}%"),
                usersModel.User.vname.ilike(f"%{vsearch}%"),
                labModel.Lab.vname.ilike(f"%{vsearch}%"),
            )
        )

    if nstatus is not None:
        query = query.filter(Booking.nstatus == nstatus)
    if nid_facility is not None:
        query = query.filter(LabFacility.nid_facility == nid_facility)
    if nid_lab is not None:
        query = query.filter(LabFacility.nid_lab == nid_lab)
    
    # Filter tanggal (wajib ada)
    if dstart is not None and dend is not None:
        query = query.filter(
            func.date(Booking.dstart) <= dend,
            func.date(Booking.dend) >= dstart
        )
    elif dstart is not None:
        query = query.filter(func.date(Booking.dend) >= dstart)
    elif dend is not None:
        query = query.filter(func.date(Booking.dstart) <= dend)
    # --- SELESAI LOGIC FILTER ---

    # [PERBEDAAN] Langsung .all() tanpa skip/limit/total
    results = query.order_by(Booking.dsort_at.desc()).all()

    return results

def get_oldest_waiting_doc_bookings(
    db: Session,
    current_user: usersModel.User,
    user_roles: Set[str],
    limit: int = 3
):
    """
    Mengambil booking dengan status 'Waiting For Documentation' (4) yang paling lama (oldest).
    Data di-scope berdasarkan role user (PIC -> Lab, Admin -> Dept, SA -> All).
    """
    # 1. Ambil ID Lab yang dikelola user
    managed_lab_ids = get_managed_lab_ids(db, current_user, user_roles)
    
    if not managed_lab_ids:
        return []

    # 2. Query Booking
    query = db.query(Booking).options(
        joinedload(Booking.user),
        joinedload(Booking.lab_facility).joinedload(LabFacility.lab),
        joinedload(Booking.lab_facility).joinedload(LabFacility.facility),
        selectinload(Booking.booking_files).joinedload(BookingFile.file)
    ).join(
        LabFacility, Booking.nid_lab_facility == LabFacility.nid
    ).filter(
        Booking.nstatus == 4, # Waiting For Documentation
        LabFacility.nid_lab.in_(managed_lab_ids) # Scoping
    )

    # 3. Order by Created At (Oldest First) & Limit
    results = query.order_by(Booking.dcreated_at.asc()).limit(limit).all()

    return results


def count_maintenance_conflicts(
    db: Session,
    lab_facility_id: int,
    start_date: datetime,
    end_date: datetime
) -> int:
    """
    Menghitung jumlah booking yang konflik (Approved, Pending, WaitingDoc, Done)
    untuk keperluan pengecekan maintenance.
    """

    conflict_statuses = [1, 2]
    
    count = db.query(Booking).filter(
        Booking.nid_lab_facility == lab_facility_id,
        Booking.nstatus.in_(conflict_statuses),
        Booking.dstart < end_date,
        Booking.dend > start_date
    ).count()
    
    return count


def cancel_conflicting_bookings(
    db: Session,
    lab_facility_id: int,
    start_date: datetime,
    end_date: datetime,
    current_user: usersModel.User
) -> List[dict]:
    """
    Menangani booking yang konflik dengan jadwal maintenance.
    Returns: List of dicts {'type': 'full'|'partial', 'booking': Booking, 'original_code': str}
    Logic:
    1. Full Overlap (Booking inside Maintenance) -> Cancel
    2. Split (Maintenance inside Booking) -> Resize original + Create new booking
    3. Overlap at End (Booking ends inside Maintenance) -> Resize end
    4. Overlap at Start (Booking starts inside Maintenance) -> Resize start
    """
    conflict_statuses = [1, 2] # Approved, Pending
    
    # Ensure inputs are aware
    start_date = to_wib(start_date)
    end_date = to_wib(end_date)
    
    # Load relationships for email notification
    conflicting_bookings = db.query(Booking).options(
        joinedload(Booking.user),
        joinedload(Booking.lab_facility).joinedload(LabFacility.lab)
    ).filter(
        Booking.nid_lab_facility == lab_facility_id,
        Booking.nstatus.in_(conflict_statuses),
        Booking.dstart < end_date,
        Booking.dend > start_date
    ).all()
    
    cancelled_list = []
    
    for booking in conflicting_bookings:
        b_start = to_wib(booking.dstart)
        b_end = to_wib(booking.dend)
        original_code = booking.vcode
        
        # Calculate Overlap
        overlap_start = max(b_start, start_date)
        overlap_end = min(b_end, end_date)
        
        if overlap_start >= overlap_end:
            continue # No actual overlap
            
        # Check if it's a full overlap
        is_full_overlap = (b_start >= start_date and b_end <= end_date)
        
        if is_full_overlap:
            # Case 1: Full Overlap -> Just cancel the original
            booking.nstatus = 3 # Canceled
            booking.dcanceled_at = now_wib()
            booking.vmodified_by = current_user.vcode
            booking.dsort_at = now_wib()
            cancelled_list.append({
                'type': 'full',
                'booking': booking,
                'original_code': original_code
            })
        else:
            # Partial Overlap -> We need to handle the overlap and the remainder
            
            # 1. Create a Clone for the Overlapping Part (Marked as Cancelled)
            cancel_code = generate_unique_booking_code(db)
            cancelled_clone = Booking(
                vcode=cancel_code,
                nid_lab_facility=booking.nid_lab_facility,
                nid_user=booking.nid_user,
                dstart=overlap_start,
                dend=overlap_end,
                vactivity=booking.vactivity,
                nstatus=3, # Cancelled
                nbooking_type=booking.nbooking_type,
                dcreated_at=now_wib(),
                vcreated_by=current_user.vcode,
                dcanceled_at=now_wib(),
                dsort_at=now_wib()
            )
            # Manually attach relationships to clone for notification purpose
            cancelled_clone.user = booking.user
            cancelled_clone.lab_facility = booking.lab_facility
            
            # Helper to clamp start time to 08:00 if it's earlier
            def adjust_start_to_working_hours(dt: datetime) -> datetime:
                # If time is before 08:00, set it to 08:00
                if dt.hour < 8:
                    return dt.replace(hour=8, minute=0, second=0, microsecond=0)
                return dt

            remaining_schedule = []
            if b_start < start_date and b_end > end_date:
                 # Remainder 1 (Before Maintenance)
                 remaining_schedule.append({'start': b_start, 'end': start_date})
                 
                 # Remainder 2 (After Maintenance)
                 new_start_2 = adjust_start_to_working_hours(end_date)
                 if new_start_2 < b_end:
                    remaining_schedule.append({'start': new_start_2, 'end': b_end})
                    
            elif b_start < start_date:
                 remaining_schedule.append({'start': b_start, 'end': start_date})
                 
            elif b_end > end_date:
                 new_start = adjust_start_to_working_hours(end_date)
                 if new_start < b_end:
                    remaining_schedule.append({'start': new_start, 'end': b_end})

            db.add(cancelled_clone)
            cancelled_list.append({
                'type': 'partial',
                'booking': cancelled_clone,
                'original_code': original_code,
                'remaining_schedule': remaining_schedule
            })
            
            # 2. Resize/Split the Original Booking
            
            # Case 2: Split (Booking covers before and after Maintenance)
            if b_start < start_date and b_end > end_date:
                # Resize Original to end at overlap start
                booking.dend = start_date
                booking.vmodified_by = current_user.vcode
                booking.dsort_at = now_wib()
                
                # Create Clone for the remainder (after overlap end)
                new_start_clone = adjust_start_to_working_hours(end_date)
                
                if new_start_clone < b_end:
                    remainder_code = generate_unique_booking_code(db)
                    remainder_clone = Booking(
                        vcode=remainder_code,
                        nid_lab_facility=booking.nid_lab_facility,
                        nid_user=booking.nid_user,
                        dstart=new_start_clone,
                        dend=b_end,
                        vactivity=booking.vactivity,
                        nstatus=booking.nstatus, # Keep original status
                        nbooking_type=booking.nbooking_type,
                        dcreated_at=now_wib(),
                        vcreated_by=current_user.vcode,
                        dsort_at=now_wib()
                    )
                    db.add(remainder_clone)
                
            # Case 3: Overlap at End (Booking starts before, ends inside Maintenance)
            elif b_start < start_date:
                # Resize Original to end at overlap start
                booking.dend = start_date
                booking.vmodified_by = current_user.vcode
                booking.dsort_at = now_wib()
                
            # Case 4: Overlap at Start (Booking starts inside, ends after Maintenance)
            elif b_end > end_date:
                # Resize Original to start at overlap end
                new_start_original = adjust_start_to_working_hours(end_date)
                
                if new_start_original < b_end:
                    booking.dstart = new_start_original
                    booking.vmodified_by = current_user.vcode
                    booking.dsort_at = now_wib()
                else:
                    # If the adjusted start is after end, the booking is effectively gone
                    booking.nstatus = 3 # Cancelled
                    booking.dcanceled_at = now_wib()
                    booking.vmodified_by = current_user.vcode
            
        
    if cancelled_list:
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Gagal memproses booking konflik: {str(e)}")
            
    return cancelled_list

def set_booking_maintenance(
    nid_lab: int,
    nid_facility: Optional[int],
    vactivity: str,
    dstart: datetime,
    dend: datetime,
    force: bool,
    db: Session,
    current_user: usersModel.User
):
    # 1. Identify Target Facilities
    target_facilities = []
    
    # Fetch Lab Info for Error Messages
    lab_info = f"Lab ID: {nid_lab}" # Default fallback
    lab_obj = db.query(labModel.Lab).filter(labModel.Lab.nid == nid_lab).first()
    if lab_obj:
        lab_info = f"{lab_obj.vname} ({lab_obj.vcode})"

    if nid_facility:
        # Single Facility Mode
        fac = db.query(LabFacility).filter(
            LabFacility.nid_lab == nid_lab,
            LabFacility.nid_facility == nid_facility,
            LabFacility.nstatus == 1
        ).first()
        if not fac:
            # Fetch Facility Info for Error Message
            fac_info = f"Fasilitas ID: {nid_facility}"
            fac_obj = db.query(facilityModel.Facility).filter(facilityModel.Facility.nid == nid_facility).first()
            if fac_obj:
                fac_info = f"{fac_obj.vname} ({fac_obj.vcode})"
            
            raise HTTPException(status_code=404, detail=f"Kombinasi {lab_info} dan {fac_info} tidak ditemukan atau tidak aktif.")
        target_facilities.append(fac)
    else:
        # All Facilities Mode
        target_facilities = db.query(LabFacility).filter(
            LabFacility.nid_lab == nid_lab,
            LabFacility.nstatus == 1
        ).all()
        if not target_facilities:
             raise HTTPException(status_code=404, detail=f"Tidak bisa melakukan booking maintenance pada {lab_info} karena tidak ada fasilitas aktif yang ditemukan.")

    # 2. Check Conflicts (Aggregate)
    total_conflicts = 0
    for fac in target_facilities:
        count = count_maintenance_conflicts(
            db, lab_facility_id=fac.nid,
            start_date=dstart, end_date=dend
        )
        total_conflicts += count
    
    if total_conflicts > 0 and not force:
        raise HTTPException(
            status_code=409, 
            detail=f"Booking conflict: Terdapat total {total_conflicts} booking yang konflik dengan jadwal maintenance ini di seluruh fasilitas yang dipilih."
        )

    # 3. Process Maintenance
    all_cancelled_bookings = []
    created_bookings = []
    
    try:
        for fac in target_facilities:
            # Cancel conflicts if force
            if total_conflicts > 0 and force:
                cancelled = cancel_conflicting_bookings(
                    db, fac.nid, dstart, dend, current_user
                )
                all_cancelled_bookings.extend(cancelled)
            
            # Create Maintenance Booking
            new_code = generate_unique_booking_code(db)
            new_maintenance = Booking(
                vcode=new_code,
                nid_lab_facility=fac.nid,
                nid_user=current_user.nid,
                dstart=dstart,
                dend=dend,
                vactivity="Maintenance: " + vactivity,
                nstatus=1, # Approved by default for maintenance
                nbooking_type=1, # Maintenance
                dcreated_at=now_wib(),
                vcreated_by=current_user.vcode
            )
            db.add(new_maintenance)
            created_bookings.append(new_maintenance)
        
        db.commit()
        for b in created_bookings:
            db.refresh(b)
            
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal membuat jadwal maintenance: {str(e)}")

    # Return result
    # We return the first booking to satisfy the API response structure expected by the caller
    primary_booking = created_bookings[0] if created_bookings else None
    
    return {
        "message": f"Jadwal maintenance berhasil dibuat untuk {len(created_bookings)} fasilitas.",
        "booking": BookingSchema.model_validate(primary_booking).model_dump(mode='json') if primary_booking else None,
        "conflicts_resolved": len(all_cancelled_bookings) if force else 0,
        "cancelled_bookings": all_cancelled_bookings 
    }

def get_lab_utilization_stats(db: Session):
    """
    Mengambil statistik utilisasi lab berdasarkan jumlah booking
    dalam 30 hari terakhir. Termasuk lab dengan 0 booking.
    """
    thirty_days_ago = now_wib() - timedelta(days=30)
    
    # Subquery untuk filter booking 30 hari terakhir (SEMUA STATUS)
    # Kita perlu ini supaya filter tanggal tidak membuang Lab yang tidak punya booking di range tsb
    subquery_booking = db.query(
        Booking.nid_lab_facility,
        Booking.nid
    ).filter(
        Booking.dstart >= thirty_days_ago
    ).subquery()

    results = db.query(
        labModel.Lab.vname,
        func.count(subquery_booking.c.nid).label('booking_count')
    ).outerjoin(
        LabFacility, labModel.Lab.nid == LabFacility.nid_lab
    ).outerjoin(
        subquery_booking, LabFacility.nid == subquery_booking.c.nid_lab_facility
    ).filter(
        labModel.Lab.nstatus == 1 # Hanya lab aktif
    ).group_by(
        labModel.Lab.nid, labModel.Lab.vname
    ).order_by(
        desc('booking_count')
    ).all()
    
    stats = [
        {"lab_name": r.vname, "booking_count": r.booking_count}
        for r in results
    ]
    
    return stats


# --- PUBLIC ENDPOINTS ---

def get_public_bookings_by_lab(
    db: Session,
    lab_vcode: str,
    dstart: datetime,
    dend: datetime,
    nid_facility: Optional[int] = None
):
    """
    Get approved/done bookings for a specific lab (public access).
    Only returns: Approved (1), WaitingForDoc (4), Done (5) bookings.
    Also includes Maintenance (nbooking_type=1).
    """
    # Get lab by vcode
    lab = db.query(labModel.Lab).filter(
        labModel.Lab.vcode == lab_vcode,
        labModel.Lab.nstatus == 1
    ).first()
    
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")
    
    # Query bookings for this lab
    # Status: 1=Approved
    approved_statuses = [1]
    
    query = db.query(
        Booking.vcode,
        Booking.dstart,
        Booking.dend,
        Booking.vactivity,
        Booking.nstatus,
        Booking.nbooking_type,
        facilityModel.Facility.vname.label('facility_name')
    ).join(
        LabFacility, Booking.nid_lab_facility == LabFacility.nid
    ).join(
        facilityModel.Facility, LabFacility.nid_facility == facilityModel.Facility.nid
    ).filter(
        LabFacility.nid_lab == lab.nid,
        Booking.nstatus.in_(approved_statuses),
        Booking.dstart < dend,
        Booking.dend > dstart
    )

    if nid_facility:
        query = query.filter(LabFacility.nid == nid_facility)

    results = query.order_by(
        Booking.dstart.asc()
    ).all()
    
    # Convert to list of dicts matching BookingPublicSchema
    return [
        {
            "vcode": r.vcode,
            "dstart": r.dstart,
            "dend": r.dend,
            "vactivity": r.vactivity,
            "nstatus": r.nstatus,
            "nbooking_type": r.nbooking_type,
            "facility_name": r.facility_name
        }
        for r in results
    ]


def get_public_bookings_all(
    db: Session,
    dstart: datetime,
    dend: datetime,
    lab_vcode: Optional[str] = None,
    nid_facility: Optional[int] = None
):
    """
    Get all approved bookings and maintenance from all labs (public access).
    Only returns: Approved (1) regular bookings and all Maintenance (nbooking_type=1).
    """
    # Status: 1=Approved for regular bookings
    approved_status = 1
    
    query = db.query(
        Booking.vcode,
        Booking.dstart,
        Booking.dend,
        Booking.vactivity,
        Booking.nstatus,
        Booking.nbooking_type,
        facilityModel.Facility.vname.label('facility_name'),
        labModel.Lab.vcode.label('lab_vcode'),
        labModel.Lab.vname.label('lab_name')
    ).join(
        LabFacility, Booking.nid_lab_facility == LabFacility.nid
    ).join(
        facilityModel.Facility, LabFacility.nid_facility == facilityModel.Facility.nid
    ).join(
        labModel.Lab, LabFacility.nid_lab == labModel.Lab.nid
    ).filter(
        labModel.Lab.nstatus == 1,  # Only active labs
        Booking.dstart < dend,
        Booking.dend > dstart,
        # Include: Approved regular bookings OR any Maintenance bookings
        or_(
            and_(Booking.nstatus == approved_status, Booking.nbooking_type == 0),  # Regular approved
            Booking.nbooking_type == 1  # Maintenance (any status)
        )
    )

    # Optional filter by lab
    if lab_vcode:
        query = query.filter(labModel.Lab.vcode == lab_vcode)
    
    # Optional filter by facility
    if nid_facility:
        query = query.filter(LabFacility.nid == nid_facility)

    results = query.order_by(
        Booking.dstart.asc()
    ).all()
    
    # Convert to list of dicts matching BookingPublicAllSchema
    return [
        {
            "vcode": r.vcode,
            "dstart": r.dstart,
            "dend": r.dend,
            "vactivity": r.vactivity,
            "nstatus": r.nstatus,
            "nbooking_type": r.nbooking_type,
            "facility_name": r.facility_name,
            "lab_vcode": r.lab_vcode,
            "lab_name": r.lab_name
        }
        for r in results
    ]

