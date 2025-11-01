from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import func, or_
from fastapi import HTTPException, Request, UploadFile
import uuid
import secrets
from datetime import datetime
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

from ..schemas.bookingSchema import BookingSchema
from ..schemas.bookingFilesSchema import BookingFileCreate

from . import fileController

# --- HELPERS ---

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
                    vcreated_by=current_user.vcode
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
            vcreated_by=current_user.vcode
        )
        db.add(db_file)
        return True

def trigger_update_overdue_bookings(db: Session):
    now = datetime.now()
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
        booking.dreviewed_at = None
        booking.vreviewed_by = None
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
    vsearch: str = ""
):
    base_query = db.query(Booking).options(
        joinedload(Booking.user),
        joinedload(Booking.lab_facility).joinedload(LabFacility.lab),
        joinedload(Booking.lab_facility).joinedload(LabFacility.facility),
        selectinload(Booking.booking_files).joinedload(BookingFile.file)
    ).filter(Booking.nstatus != 0)

    managed_lab_ids = get_managed_lab_ids(db, current_user, user_roles)
    
    if not managed_lab_ids:
         return {"data": [], "total": 0}
    
    base_query = base_query.join(
        LabFacility, Booking.nid_lab_facility == LabFacility.nid
    ).filter(
        LabFacility.nid_lab.in_(managed_lab_ids)
    )

    if vsearch:
        base_query = base_query.join(Booking.user).join(labModel.Lab, LabFacility.nid_lab == labModel.Lab.nid)
        base_query = base_query.filter(
            or_(
                Booking.vcode.ilike(f"%{vsearch}%"),
                Booking.vactivity.ilike(f"%{vsearch}%"),
                usersModel.User.vname.ilike(f"%{vsearch}%"),
                labModel.Lab.vname.ilike(f"%{vsearch}%"),
            )
        )

    total = base_query.count()
    results = base_query.order_by(Booking.dcreated_at.desc()).offset(skip).limit(limit).all()

    return {"data": results, "total": total}


def get_all_bookings_by_user(
    db: Session,
    current_user: usersModel.User,
    skip: int = 0,
    limit: int = 10,
    vsearch: str = ""
):
    base_query = db.query(Booking).options(
        joinedload(Booking.lab_facility).joinedload(LabFacility.lab),
        joinedload(Booking.lab_facility).joinedload(LabFacility.facility),
        selectinload(Booking.booking_files).joinedload(BookingFile.file)
    ).filter(Booking.nid_user == current_user.nid, Booking.nstatus != 0)
    
    if vsearch:
         base_query = base_query.join(Booking.lab_facility).join(labModel.Lab, LabFacility.nid_lab == labModel.Lab.nid).filter(
            or_(
                Booking.vcode.ilike(f"%{vsearch}%"), Booking.vactivity.ilike(f"%{vsearch}%"),
                labModel.Lab.vname.ilike(f"%{vsearch}%"),
            )
        )
         
    total = base_query.count()
    results = base_query.order_by(Booking.dcreated_at.desc()).offset(skip).limit(limit).all()
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

async def create_booking(db: Session, current_user: usersModel.User, request: Request, nid_lab_facility: int, dstart: datetime, dend: datetime, vactivity: str, proposal_file: UploadFile):
    if dend <= dstart:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    
    lab_facility = db.query(LabFacility).get(nid_lab_facility)
    if not lab_facility or lab_facility.nstatus != 1:
        raise HTTPException(status_code=404, detail="Lab/Facility not found or not active")
        
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
            current_user=current_user, request=request, is_public=False
        )
        if not db_proposal_file:
             raise HTTPException(status_code=500, detail="Gagal menyimpan file proposal.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memproses file: {str(e)}")
        
    try:
        new_booking_code = generate_unique_booking_code(db)
        db_booking = Booking(
            vcode=new_booking_code, nid_lab_facility=nid_lab_facility,
            nid_user=current_user.nid, dstart=dstart, dend=dend,
            vactivity=vactivity, nstatus=2, vcreated_by=current_user.vcode
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
            raise HTTPException(status_code=409, detail="Konflik booking: Slot ini sudah di-approve untuk booking lain.")

        is_scoped = check_booking_lab_scope(db, current_user, user_roles, booked_lab_id)
        if not is_scoped:
            raise HTTPException(status_code=403, detail="Otorisasi gagal: Anda hanya bisa approve booking di Lab yang Anda kelola.")

        db_booking.nstatus = new_status
        db_booking.dreviewed_at = datetime.now()
        db_booking.vreviewed_by = current_user.vcode
        modified = True
    
    elif new_status == 0: # Reject
        if old_status != 2:
            raise HTTPException(status_code=409, detail=f"Booking hanya bisa di-reject dari status Pending (2).")
        
        is_scoped = check_booking_lab_scope(db, current_user, user_roles, booked_lab_id)
        if not is_scoped:
            raise HTTPException(status_code=403, detail="Otorisasi gagal: Anda hanya bisa reject booking di Lab yang Anda kelola.")
        
        db_booking.nstatus = new_status
        db_booking.dreviewed_at = datetime.now() # Catat waktu reject
        db_booking.vreviewed_by = current_user.vcode # Catat siapa yg reject
        modified = True

    elif new_status == 3: # Cancel
        is_owner = db_booking.nid_user == current_user.nid
        if not is_owner and not is_management:
            raise HTTPException(status_code=403, detail="Hanya owner atau admin/PIC/SA yang bisa cancel.")
        if old_status not in [1, 2]:
             raise HTTPException(status_code=409, detail="Booking can only be canceled if Pending or Approved")
        
        db_booking.nstatus = new_status
        if old_status == 1:
            db_booking.dreviewed_at = None
            db_booking.vreviewed_by = None
        modified = True

    elif new_status in [4, 5]: # Manual Override
         if 'SA' not in user_roles and 'ADM' not in user_roles:
             raise HTTPException(status_code=403, detail="Hanya Admin atau Superadmin yang bisa ganti status manual ke 4 atau 5.")
        
         db_booking.nstatus = new_status
         if old_status == 1:
            db_booking.dreviewed_at = None
            db_booking.vreviewed_by = None
         modified = True
    
    else:
         raise HTTPException(status_code=400, detail=f"Invalid status change: {old_status} to {new_status}")

    if modified:
        try:
            db_booking.vmodified_by = current_user.vcode
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
                    current_user=current_user, request=request, is_public=False
                )
                new_image_ids.append(db_img_file.nid)
                list_of_new_file_ids_to_rollback.append(db_img_file.nid)
            if replace_booking_files_by_type(db, booking_id, "documentation_image", new_image_ids, current_user):
                modified = True
                files_uploaded_in_this_request = True
        
        if has_doc_article:
            db_article_file = await fileController.save_file(
                db=db, file=doc_article, category="bookingDocs",
                current_user=current_user, request=request, is_public=False
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
    db_booking.vmodified_by = current_user.vcode
    db.commit()

    return {"detail": "Booking successfully deleted (soft delete)"}

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
        
        # 2. Ambil data reviewer (admin/pic)
        db_reviewer = db.query(usersModel.User).filter(
            usersModel.User.nid == reviewer_nid
        ).first()

        if not db_booking or not db_reviewer:
            print(f"[Notify User] Error: Booking ID {booking_id} atau Reviewer NID {reviewer_nid} tidak ditemukan.")
            return

        booked_lab = db_booking.lab_facility.lab
        booked_user = db_booking.user
        
        new_status_str = "Tidak Diketahui"
        if new_status == 1:
            new_status_str = "Disetujui"
        elif new_status == 0:
            new_status_str = "Ditolak"
        
        if db_booking.dreviewed_at is None:
            print(f"[Notify User] WARNING: dreviewed_at masih None untuk booking {booking_id}. Pake waktu sekarang.")
            review_time = datetime.now()
        else:
            review_time = db_booking.dreviewed_at

        # 3. Kirim email
        await email_service.send_booking_status_email(
            recipient_email=booked_user.vemail,
            user_name=booked_user.vname,
            booking_code=db_booking.vcode,
            lab_name=booked_lab.vname,
            activity=db_booking.vactivity,
            new_status_str=new_status_str,
            reviewer_name=db_reviewer.vname,
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