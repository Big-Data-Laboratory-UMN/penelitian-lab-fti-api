from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import func, or_
from fastapi import HTTPException, Request, UploadFile
import uuid
from datetime import datetime
from typing import Optional, List, Set

# Import model
from ..models.bookingModel import Booking
from ..models.bookingFilesModel import BookingFile
from ..models.labFacilityModel import LabFacility
from ..models import usersModel, rolesModel, labModel, facilityModel, filesModel

# Import model baru
from ..models.userAccessModel import UserAccess 
from ..models.departmentLabModel import DepartmentLab

from ..schemas.bookingSchema import BookingSchema
from ..schemas.bookingFilesSchema import BookingFileCreate

from . import fileController 

# --- [FIXED] HELPER BARU ---
def get_managed_lab_ids(db: Session, current_user: usersModel.User, user_roles: Set[str]) -> List[int]:
    """
    Mengambil list NID Lab unik yang bisa di-manage oleh user (SA, ADM, atau PIC)
    berdasarkan assignment EKSPLISIT di tblr_user_access.
    """
    if 'VSTR' in user_roles:
        return []

    # 1. Ambil semua NID Lab yang di-assign ke user ini, yang tidak NULL
    user_access_records = db.query(UserAccess.nid_lab).filter(
        UserAccess.nid_user == current_user.nid,
        UserAccess.nid_lab != None, # Pastikan nid_lab ada isinya
        UserAccess.nstatus == 1
    ).distinct().all() # Ambil yang unik

    # 2. Ubah dari [Row(1,), Row(2,)] -> [1, 2]
    managed_lab_ids = [record.nid_lab for record in user_access_records]
    
    return managed_lab_ids

# --- [FIXED] HELPER BARU ---
def check_booking_lab_scope(
    db: Session, 
    current_user: usersModel.User, 
    user_roles: Set[str], 
    booking_lab_id: int
) -> bool:
    """
    Mengecek apakah user punya hak akses (SA/ADM/PIC) ke booking_lab_id spesifik.
    """
    # Logic ini jadi simple: Cek aja user ini punya row di tblr_user_access
    # yang ngasih dia akses ke lab_id ini.
    
    has_access = db.query(UserAccess).filter(
        UserAccess.nid_user == current_user.nid,
        UserAccess.nid_lab == booking_lab_id, # Langsung cek ke lab-nya
        UserAccess.nstatus == 1
    ).first()

    return has_access is not None

# --- FUNGSI HELPER LAMA ---
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
    # ... (Isi fungsi sama)
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
    # ... (Isi fungsi sama)
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
    # ... (Isi fungsi sama)
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
        booking.dapproved_at = None
        booking.vapproved_by = None
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

# --- FUNGSI CRUD UTAMA ---

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

    # [FIXED] Panggil helper baru yg udah bener
    managed_lab_ids = get_managed_lab_ids(db, current_user, user_roles)
    
    if not managed_lab_ids:
         # Kalo dia ADM/PIC tapi gak ke-assign apa2, return data kosong
         return {"data": [], "total": 0}
    
    # Filter booking berdasarkan NID Lab yang di-manage
    base_query = base_query.join(
        LabFacility, Booking.nid_lab_facility == LabFacility.nid
    ).filter(
        LabFacility.nid_lab.in_(managed_lab_ids)
    )

    if vsearch:
        # Join-nya udah ada dari filter scope di atas
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
    # ... (Isi fungsi sama)
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
    # ... (Isi fungsi sama)
    db_booking = db.query(Booking).options(
        joinedload(Booking.user), 
        joinedload(Booking.lab_facility).joinedload(LabFacility.lab),
        joinedload(Booking.lab_facility).joinedload(LabFacility.facility),
        selectinload(Booking.booking_files).joinedload(BookingFile.file)
    ).filter(Booking.nid == booking_id, Booking.nstatus != 0).first()
    if not db_booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return db_booking

async def create_booking(db: Session, current_user: usersModel.User, request: Request, nid_lab_facility: int, dstart: datetime, dend: datetime, vactivity: str, proposal_file: UploadFile):
    # ... (Isi fungsi sama)
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
        db_booking = Booking(
            vcode=str(uuid.uuid4()), nid_lab_facility=nid_lab_facility,
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


async def update_booking(
    db: Session,
    booking_id: int,
    current_user: usersModel.User,
    request: Request,
    nstatus: Optional[int],
    doc_images: List[UploadFile],
    doc_article: Optional[UploadFile]
):
    # ... (Isi fungsi sama, tapi logic scope-nya udah bener sekarang)
    user_access_records = db.query(rolesModel.Role.vcode).join(
        UserAccess, rolesModel.Role.nid == UserAccess.nid_role
    ).filter(UserAccess.nid_user == current_user.nid, UserAccess.nstatus == 1).all()
    user_roles = {role[0] for role in user_access_records}
    is_management = 'ADM' in user_roles or 'SA' in user_roles or 'PIC' in user_roles

    db_booking = db.query(Booking).options(
        joinedload(Booking.lab_facility)
    ).filter(
        Booking.nid == booking_id
    ).with_for_update().first()

    if not db_booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if db_booking.nstatus == 0:
        raise HTTPException(status_code=404, detail="Booking already deleted")

    modified = False
    files_uploaded_in_this_request = False
    list_of_new_file_ids_to_rollback = []
    
    booked_lab_id = db_booking.lab_facility.nid_lab

    has_doc_images = doc_images and len(doc_images) > 0 and doc_images[0].filename
    has_doc_article = doc_article and doc_article.filename

    # --- LOGIC 1: GANTI STATUS (Approve/Reject) ---
    if nstatus is not None:
        if not is_management:
            raise HTTPException(status_code=403, detail="Hanya Admin, PIC, atau Superadmin yang bisa ganti status.")
        
        new_status = nstatus
        old_status = db_booking.nstatus

        if new_status == old_status:
            pass 
        
        elif new_status == 1: # Approve
            if old_status != 2:
                raise HTTPException(status_code=409, detail=f"Booking hanya bisa di-approve dari status Pending (2).")
            
            is_available = check_booking_availability(
                db, lab_facility_id=db_booking.nid_lab_facility,
                start_date=db_booking.dstart, end_date=db_booking.dend
            )
            if not is_available:
                raise HTTPException(status_code=409, detail="Konflik booking: Slot ini sudah di-approve untuk booking lain.")

            # [FIXED] Panggil helper baru yg udah bener
            is_scoped = check_booking_lab_scope(db, current_user, user_roles, booked_lab_id)
            if not is_scoped:
                raise HTTPException(status_code=403, detail="Otorisasi gagal: Anda hanya bisa approve booking di Lab yang Anda kelola.")

            db_booking.nstatus = new_status
            db_booking.dapproved_at = datetime.now()
            db_booking.vapproved_by = current_user.vcode
            modified = True
        
        elif new_status == 0: # Reject
            if old_status != 2:
                raise HTTPException(status_code=409, detail=f"Booking hanya bisa di-reject dari status Pending (2).")
            
            is_scoped = check_booking_lab_scope(db, current_user, user_roles, booked_lab_id)
            if not is_scoped:
                raise HTTPException(status_code=403, detail="Otorisasi gagal: Anda hanya bisa reject booking di Lab yang Anda kelola.")
            
            db_booking.nstatus = new_status
            modified = True

        else: # Status lain (3, 4, 5)
            if new_status == 3:
                is_owner = db_booking.nid_user == current_user.nid
                if not is_owner and not is_management:
                    raise HTTPException(status_code=403, detail="Hanya owner atau admin/PIC/SA yang bisa cancel.")
                if old_status not in [1, 2]:
                     raise HTTPException(status_code=409, detail="Booking can only be canceled if Pending or Approved")
            
            elif new_status in [4, 5]:
                 if 'SA' not in user_roles and 'ADM' not in user_roles:
                     raise HTTPException(status_code=403, detail="Hanya Admin atau Superadmin yang bisa ganti status manual.")
            
            else:
                 raise HTTPException(status_code=400, detail=f"Invalid status change: {old_status} to {new_status}")
            
            db_booking.nstatus = new_status
            if old_status == 1: 
                db_booking.dapproved_at = None
                db_booking.vapproved_by = None
            modified = True

    # --- LOGIC 2: UPLOAD DOKUMEN (Oleh User) ---
    if has_doc_images or has_doc_article:
        
        if nstatus is not None:
            raise HTTPException(status_code=400, detail="Cannot change status and upload files in the same request.")
        
        if db_booking.nstatus != 4:
            raise HTTPException(
                status_code=409, 
                detail=f"Cannot upload documentation. Booking status is '{db_booking.nstatus}', must be 'Waiting For Documentation (4)'."
            )
        
        if db_booking.nid_user != current_user.nid:
             raise HTTPException(status_code=403, detail="Hanya user pembuat booking yang bisa upload dokumentasi.")

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
        except Exception as e:
            for file_id in list_of_new_file_ids_to_rollback:
                try: fileController.permanently_delete_file_record(db, file_id)
                except Exception: pass
            raise HTTPException(status_code=500, detail=f"Gagal memproses file dokumentasi: {str(e)}")

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
            db.commit()
            db.refresh(db_booking)
        except Exception as e:
            db.rollback()
            for file_id in list_of_new_file_ids_to_rollback:
                try: fileController.permanently_delete_file_record(db, file_id)
                except Exception: pass
            raise HTTPException(status_code=500, detail=f"Gagal menyimpan update booking: {str(e)}")

    return get_booking_by_id(db, db_booking.nid)


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