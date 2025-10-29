from sqlalchemy.orm import Session, selectinload, joinedload # [FIX 1] Import Eager Loading
from sqlalchemy import func, or_
from fastapi import HTTPException
import uuid
from datetime import datetime
from typing import Optional, List

# Import model & schema
from ..models.bookingModel import Booking
from ..models.bookingFilesModel import BookingFile
from ..models.labFacilityModel import LabFacility
from ..models import usersModel, rolesModel, labModel, facilityModel, filesModel
from ..models.userAccessModel import UserAccess 

# Import Schema
from ..schemas.bookingSchema import BookingCreate, BookingUpdate, BookingSchema
from ..schemas.bookingFilesSchema import BookingFileCreate

# --- FUNGSI HELPER (YANG LAMA TETAP SAMA) ---

def check_booking_availability(
    db: Session,
    lab_facility_id: int,
    start_date: datetime,
    end_date: datetime,
    exclude_booking_id: Optional[int] = None
):
    """
    [SESUAI FLOW] Cek ketersediaan HANYA terhadap status 1 (Approved)
    """
    booked_statuses = [1] # Approved
    query = db.query(Booking).filter(
        Booking.nid_lab_facility == lab_facility_id,
        Booking.nstatus.in_(booked_statuses),
        Booking.dstart < end_date,
        Booking.dend > start_date
    )
    if exclude_booking_id:
        query = query.filter(Booking.nid != exclude_booking_id)
    return query.count() == 0

def replace_booking_files_by_type(
    db: Session,
    booking_id: int,
    file_type: str,
    new_file_ids: List[int],
    current_user: usersModel.User
):
    # (Logika sama, udah bener)
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
                    vcode=str(uuid.uuid4()),
                    nid_booking=booking_id,
                    nid_file=file_id,
                    vtype=file_type,
                    vcreated_by=current_user.vcode
                )
            )
        db.add_all(new_files)
    return len(new_files) > 0

def upsert_booking_file(
    db: Session,
    booking_id: int,
    file_type: str,
    new_file_id: Optional[int],
    current_user: usersModel.User
):
    # (Logika sama, udah bener)
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
            vcode=str(uuid.uuid4()),
            nid_booking=booking_id,
            nid_file=new_file_id,
            vtype=file_type,
            vcreated_by=current_user.vcode
        )
        db.add(db_file)
        return True

# --- [FIX 2] HELPER BARU BUAT OTOMATISASI STATUS (1) -> (4) ---

def trigger_update_overdue_bookings(db: Session):
    """
    (ADMIN/CRON) Fungsi ini buat di-trigger scheduler (cron job).
    Dia nyari booking yg statusnya Approved (1) tapi tanggal selesainya (dend)
    udah lewat, terus diubah jadi Waiting For Documentation (4).
    """
    now = datetime.now() # Ambil waktu server
    
    # Cari booking yg status 1 (Approved) & udah lewat waktunya
    overdue_bookings = db.query(Booking).filter(
        Booking.nstatus == 1,
        Booking.dend < now 
    ).with_for_update().all() # Lock semua row yg mau di-update

    if not overdue_bookings:
        return {"updated_count": 0, "detail": "No overdue bookings found"}

    updated_ids = []
    for booking in overdue_bookings:
        booking.nstatus = 4 # Ganti status jadi Waiting For Documentation
        booking.vmodified_by = "SYSTEM_SCHEDULER" # Kasih tanda
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


# --- [FIX 1] HELPER BARU BUAT MAPPING (ANTI N+1) ---
def map_booking_to_dict(booking: Booking):
    """
    Helper buat mapping data Booking + Eager-Loaded relations ke Dictionary.
    """
    if not booking:
        return None

    booking_dict = booking.__dict__
    booking_dict.pop('_sa_instance_state', None)

    # 1. Ambil data User (dari joinedload)
    booking_dict["user_name"] = booking.user.vname if booking.user else None

    # 2. Ambil data Lab & Facility (dari nested joinedload)
    booking_dict["lab_name"] = (
        booking.lab_facility.lab.vname 
        if booking.lab_facility and booking.lab_facility.lab 
        else None
    )
    booking_dict["facility_name"] = (
        booking.lab_facility.facility.vname 
        if booking.lab_facility and booking.lab_facility.facility 
        else None
    )

    # 3. Ambil data Files (dari selectinload)
    files_list = []
    if booking.booking_files:
        for bf in booking.booking_files:
            if bf.nstatus == 1 and bf.file: # Filter nstatus=1
                files_list.append({
                    "nid": bf.nid, "vcode": bf.vcode, "nid_booking": bf.nid_booking,
                    "nid_file": bf.nid_file, "vtype": bf.vtype, "nstatus": bf.nstatus,
                    "vcreated_by": bf.vcreated_by, "dcreated_at": bf.dcreated_at,
                    "file": {
                        "nid": bf.file.nid, "vname": bf.file.vname,
                        "vpath": bf.file.vpath, "vtype": bf.file.vtype,
                        "nsize": bf.file.nsize
                    }
                })
    booking_dict["booking_files"] = files_list

    return booking_dict

# --- FUNGSI CRUD UTAMA (DENGAN FIX 1: EAGER LOADING) ---

def get_all_bookings(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    vsearch: str = ""
):
    """
    (ADMIN) Mengambil semua data booking DENGAN EAGER LOADING
    """
    base_query = db.query(Booking).options(
        joinedload(Booking.user), 
        joinedload(Booking.lab_facility).joinedload(LabFacility.lab),
        joinedload(Booking.lab_facility).joinedload(LabFacility.facility),
        selectinload(Booking.booking_files).joinedload(BookingFile.file)
    ).filter(Booking.nstatus != 0)

    if vsearch:
        base_query = base_query.join(
            Booking.user
        ).join(
            Booking.lab_facility
        ).join(
            LabFacility.lab
        ).filter(
            or_(
                Booking.vcode.ilike(f"%{vsearch}%"),
                Booking.vactivity.ilike(f"%{vsearch}%"),
                usersModel.User.vname.ilike(f"%{vsearch}%"),
                labModel.Lab.vname.ilike(f"%{vsearch}%"),
            )
        )

    total = base_query.count() 
    results = base_query.order_by(Booking.dcreated_at.desc()).offset(skip).limit(limit).all()
    data_list = [map_booking_to_dict(booking) for booking in results]

    return {"data": data_list, "total": total}


def get_all_bookings_by_user(
    db: Session,
    current_user: usersModel.User,
    skip: int = 0,
    limit: int = 10,
    vsearch: str = ""
):
    """
    (USER) Mengambil booking user ybs DENGAN EAGER LOADING
    """
    base_query = db.query(Booking).options(
        joinedload(Booking.lab_facility).joinedload(LabFacility.lab),
        joinedload(Booking.lab_facility).joinedload(LabFacility.facility),
        selectinload(Booking.booking_files).joinedload(BookingFile.file)
    ).filter(
        Booking.nid_user == current_user.nid,
        Booking.nstatus != 0
    )

    if vsearch:
         base_query = base_query.join(
             Booking.lab_facility
         ).join(
             LabFacility.lab
         ).filter(
            or_(
                Booking.vcode.ilike(f"%{vsearch}%"),
                Booking.vactivity.ilike(f"%{vsearch}%"),
                labModel.Lab.vname.ilike(f"%{vsearch}%"),
            )
        )

    total = base_query.count()
    results = base_query.order_by(Booking.dcreated_at.desc()).offset(skip).limit(limit).all()

    data_list = []
    for booking in results:
        booking_dict = map_booking_to_dict(booking)
        booking_dict["user_name"] = current_user.vname # Override
        data_list.append(booking_dict)

    return {"data": data_list, "total": total}


def get_booking_by_id(db: Session, booking_id: int):
    """
    Mengambil satu booking by ID DENGAN EAGER LOADING
    """
    db_booking = db.query(Booking).options(
        joinedload(Booking.user), 
        joinedload(Booking.lab_facility).joinedload(LabFacility.lab),
        joinedload(Booking.lab_facility).joinedload(LabFacility.facility),
        selectinload(Booking.booking_files).joinedload(BookingFile.file)
    ).filter(
        Booking.nid == booking_id, 
        Booking.nstatus != 0
    ).first()

    if not db_booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    return map_booking_to_dict(db_booking)


def create_booking(db: Session, booking_data: BookingCreate, current_user: usersModel.User):
    """
    Membuat booking baru (Logika Inti - Sesuai Flow)
    """
    if booking_data.dend <= booking_data.dstart:
        raise HTTPException(status_code=400, detail="End date must be after start date")

    lab_facility = db.query(LabFacility).get(booking_data.nid_lab_facility)
    if not lab_facility or lab_facility.nstatus != 1:
        raise HTTPException(status_code=404, detail="Lab/Facility not found or not active")

    is_available = check_booking_availability(
        db,
        lab_facility_id=booking_data.nid_lab_facility,
        start_date=booking_data.dstart,
        end_date=booking_data.dend
    )

    if not is_available:
        raise HTTPException(status_code=409, detail="Booking conflict: The selected date is not available")

    try:
        db_booking = Booking(
            vcode=str(uuid.uuid4()),
            nid_lab_facility=booking_data.nid_lab_facility,
            nid_user=current_user.nid,
            dstart=booking_data.dstart,
            dend=booking_data.dend,
            vactivity=booking_data.vactivity,
            nstatus=2, # [SESUAI FLOW] Default (2) Pending
            vcreated_by=current_user.vcode
        )
        db.add(db_booking)
        db.flush() 

        upsert_booking_file(
            db=db,
            booking_id=db_booking.nid,
            file_type="proposal",
            new_file_id=booking_data.nid_proposal_file,
            current_user=current_user
        )

        db.commit()
        db.refresh(db_booking)
        
        # Response-nya otomatis lengkap karena get_booking_by_id udah bener
        return get_booking_by_id(db, db_booking.nid) 
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create booking: {str(e)}")


def update_booking(
    db: Session,
    booking_id: int,
    update_data: BookingUpdate,
    current_user: usersModel.User
):
    """
    Update booking (Status, Dokumen)
    """

    # 1. Ambil role user (Sama)
    user_access_roles = db.query(rolesModel.Role.vcode).join(
        UserAccess, rolesModel.Role.nid == UserAccess.nid_role
    ).filter(UserAccess.nid_user == current_user.nid, UserAccess.nstatus == 1).all()
    user_roles = {role[0] for role in user_access_roles}
    is_admin_or_sa = 'ADM' in user_roles or 'SA' in user_roles

    # 2. [DATABASE LOCK DIMULAI] (Sama)
    db_booking = db.query(Booking).filter(
        Booking.nid == booking_id
    ).with_for_update().first()

    if not db_booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if db_booking.nstatus == 0:
        raise HTTPException(status_code=404, detail="Booking already deleted")

    modified = False

    # 3. === LOGIC GANTI STATUS === (Sesuai Flow)
    if update_data.nstatus is not None:
        new_status = update_data.nstatus
        old_status = db_booking.nstatus

        if new_status == old_status: # Ga ada perubahan
            pass 
        elif new_status in [1, 0]: # Approve/Reject
            if not is_admin_or_sa:
                raise HTTPException(status_code=403, detail="Only Admin or Superadmin can approve/reject bookings")
            if old_status != 2: # Hanya bisa dari Pending
                raise HTTPException(status_code=409, detail=f"Cannot approve/reject booking. Status is already '{old_status}'")
            db_booking.nstatus = new_status
            modified = True

        elif new_status == 3: # Cancel
            is_owner = db_booking.nid_user == current_user.nid
            if not is_owner and not is_admin_or_sa:
                raise HTTPException(status_code=403, detail="You can only cancel your own bookings")
            if old_status not in [1, 2]: # Hanya dari Approved atau Pending
                 raise HTTPException(status_code=409, detail="Booking can only be canceled if Pending or Approved")
            db_booking.nstatus = new_status
            modified = True

        elif new_status == 4: # Manual Set to "Waiting"
            if not is_admin_or_sa: # Cuma admin yg boleh
                raise HTTPException(status_code=403, detail="Only Admin can set status to 'Waiting'")
            db_booking.nstatus = new_status
            modified = True

        elif new_status == 5: # Manual Set to "Done"
             if not is_admin_or_sa: # Cuma admin yg boleh
                 raise HTTPException(status_code=403, detail="Only Admin can set status to 'Done'")
             db_booking.nstatus = new_status
             modified = True
        
        else: # Status lain yg ga dikenal
            raise HTTPException(status_code=400, detail=f"Invalid status change: {old_status} to {new_status}")


    # 4. === LOGIC UPLOAD FILE DOKUMENTASI ===
    # [SESUAI FLOW] User HANYA boleh upload file dokumentasi
    # kalo statusnya 4 (Waiting).
    
    files_uploaded_in_this_request = False

    if (update_data.nid_documentation_images is not None or 
        update_data.nid_documentation_article is not None):
        
        # Cek dulu statusnya
        if db_booking.nstatus != 4:
            raise HTTPException(
                status_code=409, 
                detail=f"Cannot upload documentation. Booking status is '{db_booking.nstatus}', must be 'Waiting For Documentation (4)'."
            )

    # --- Handle 2+ Foto (Logic "REPLACE") ---
    if update_data.nid_documentation_images is not None:
        is_modified = replace_booking_files_by_type(
            db=db, booking_id=db_booking.nid, file_type="documentation_image",
            new_file_ids=update_data.nid_documentation_images, current_user=current_user
        )
        if is_modified: 
            modified = True
            files_uploaded_in_this_request = True

    # --- Handle 1 Artikel (Logic "UPSERT") ---
    if update_data.nid_documentation_article is not None:
        is_modified = upsert_booking_file(
            db=db, booking_id=db_booking.nid, file_type="documentation_article",
            new_file_id=update_data.nid_documentation_article, current_user=current_user
        )
        if is_modified: 
            modified = True
            files_uploaded_in_this_request = True

    # 5. === [FIX 2] LOGIC AUTO-SET "DONE" (4) -> (5) ===
    # Cek ini KALO statusnya SEKARANG 4
    # DAN ada file yg di-upload di request INI.
    
    if db_booking.nstatus == 4 and files_uploaded_in_this_request:
        # Kita cek kelengkapan file SEKARANG (setelah di-upload)
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

        # [SESUAI FLOW] Kalo file lengkap (2+ gambar, 1 artikel)
        if image_count >= 2 and article_file is not None:
            db_booking.nstatus = 5 # Set status to 'Done'
            modified = True # modified udah pasti true sih, tp gpp

    # 6. === COMMIT PERUBAHAN ===
    if modified:
        db_booking.vmodified_by = current_user.vcode
        db.commit()
        db.refresh(db_booking)

    # 7. Ambil data terbaru yg udah di-join
    return get_booking_by_id(db, db_booking.nid)


def delete_booking(db: Session, booking_id: int, current_user: usersModel.User):
    """
    (ADMIN) Soft delete booking (set nstatus = 0) - (Sama)
    """
    # (Logika sama, udah bener)
    user_access_roles = db.query(rolesModel.Role.vcode).join(
        UserAccess, rolesModel.Role.nid == UserAccess.nid_role
    ).filter(UserAccess.nid_user == current_user.nid, UserAccess.nstatus == 1).all()
    user_roles = {role[0] for role in user_access_roles}
    if 'ADM' not in user_roles and 'SA' not in user_roles:
        raise HTTPException(status_code=403, detail="Only Admin or Superadmin can delete bookings")
    db_booking = db.query(Booking).filter(
        Booking.nid == booking_id
    ).with_for_update().first() 
    if not db_booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    db_booking.nstatus = 0
    db_booking.vmodified_by = current_user.vcode
    db.commit()

    return {"detail": "Booking successfully deleted (soft delete)"}