# services/controller/facilityController.py

import os
import uuid
import shutil
import asyncio
from pathlib import Path
from sqlalchemy import or_, UniqueConstraint, and_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from fastapi import UploadFile, HTTPException, Request

from ..models import facilityModel as models
from ..models import filesModel
from ..schemas import facilitySchema as schema
from ..schemas import filesSchema
from ..schemas import usersSchema
from . import fileController

# --- Konfigurasi ---
CONTROLLER_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CONTROLLER_DIR.parent.parent
UPLOAD_DIRECTORY = PROJECT_ROOT / "storage" / "facilities"
UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
# print(f"[*] Upload directory configured at: {UPLOAD_DIRECTORY}") # Uncomment for debugging path

ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"]
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']

# --- Fungsi Helper Get ---
def get_facility_by_code_and_name(db: Session, vcode: str, vname: str):
    return db.query(models.Facility).outerjoin(
        models.Files, models.Facility.nid_file == models.Files.nid
    ).filter(
        and_(
            models.Facility.vcode == vcode,
            models.Facility.vname == vname
        )
    ).first()

def get_facility_by_code(db: Session, facility_code: str):
    # Eager load file, pastikan relationship 'related_file_relationship' ada di model
    return db.query(models.Facility).options(
        joinedload(models.Facility.related_file_relationship)
    ).filter(models.Facility.vcode == facility_code).first()

def get_facility(db: Session, facility_id: int):
    # Eager load file
    return db.query(models.Facility).options(
        joinedload(models.Facility.related_file_relationship)
    ).filter(models.Facility.nid == facility_id).first()

# --- Fungsi Create (Dengan Lock, Validasi Tipe & File Handling) ---
async def create_facility_with_file(
    db: Session,
    facility_data: schema.FacilityCreate,
    file: UploadFile | None,
    current_user: usersSchema.User,
    request: Request
):
    user_id = current_user.nid
    app_state = request.app.state
    lock_dict_lock = app_state.lock_dict_lock
    user_upload_locks = app_state.user_upload_locks

    async with lock_dict_lock:
        if user_id not in user_upload_locks:
            user_upload_locks[user_id] = asyncio.Lock()
        user_lock = user_upload_locks[user_id]

    # print(f"[User {user_id}] Attempting lock for create...") # Debugging lock
    async with user_lock:
        # print(f"[User {user_id}] Lock acquired for create.") # Debugging lock
        new_file_nid = None
        saved_file_path_str = None
        saved_file_path = None

        if file:
            try:
                # Validasi Tipe & Ekstensi File
                if file.content_type not in ALLOWED_IMAGE_TYPES:
                    raise ValueError(f"Tipe file tidak valid: {file.content_type}. Hanya gambar (jpg, png, webp) yang diizinkan.")
                file_extension = Path(file.filename).suffix
                if file_extension.lower() not in ALLOWED_IMAGE_EXTENSIONS:
                     raise ValueError(f"Ekstensi file tidak valid: {file_extension}")

                # Proses Simpan File
                unique_filename = f"{uuid.uuid4()}{file_extension}"
                saved_file_path = UPLOAD_DIRECTORY / unique_filename
                saved_file_path_str = str(saved_file_path.resolve())

                with saved_file_path.open("wb") as buffer:
                    while chunk := await file.read(8192):
                         buffer.write(chunk)
                file_size_bytes = saved_file_path.stat().st_size

                # Buat Metadata File
                file_metadata = filesSchema.FileCreate(
                    vcode=str(uuid.uuid4()), vname=file.filename, vtype=file.content_type,
                    vpath=saved_file_path_str, vextension=file_extension, nsize=file_size_bytes,
                    vcategory="facility", nis_public=1, vcreated_by=facility_data.vcreated_by
                )
                created_file = fileController.create_file(db=db, file_data=file_metadata)
                new_file_nid = created_file.nid

            except ValueError as ve:
                 if file and not getattr(file, '_file', None) is None and not file._file.closed : await file.close()
                 raise ve # Re-raise validation error
            except Exception as file_error:
                # Cleanup file fisik jika gagal
                if saved_file_path and saved_file_path.exists():
                    try: os.remove(saved_file_path)
                    except Exception as del_err: print(f"Error deleting file on create error cleanup: {del_err}")
                if file and not getattr(file, '_file', None) is None and not file._file.closed : await file.close()
                raise ValueError(f"Gagal memproses file: {file_error}")
            finally:
                 if file and not getattr(file, '_file', None) is None and not file._file.closed :
                     await file.close()

        # Simpan Facility
        db_facility = models.Facility(**facility_data.model_dump())
        db_facility.dsort_at = datetime.utcnow()
        if new_file_nid:
            db_facility.nid_file = new_file_nid

        try:
            db.add(db_facility)
            db.commit()
            db.refresh(db_facility)
            db_facility = get_facility(db, db_facility.nid) # Re-fetch with eager loading
            # print(f"[User {user_id}] Facility created. Lock released.") # Debugging lock
            return db_facility
        except IntegrityError as e:
            db.rollback()
            # Rollback file creation
            if new_file_nid:
                try: fileController.permanently_delete_file_record(db=db, file_id=new_file_nid)
                except Exception as delete_db_error: print(f"CRITICAL: Failed rollback file (NID: {new_file_nid}): {delete_db_error}")
                # Hapus fisik (double check)
                if saved_file_path_str and os.path.exists(saved_file_path_str):
                     try: os.remove(saved_file_path_str)
                     except Exception as del_phys_error: print(f"CRITICAL: Failed delete physical file on rollback: {del_phys_error}")

            error_info = str(e.orig).lower()
            # print(f"[User {user_id}] IntegrityError on create. Lock released.") # Debugging lock
            # Raise specific errors based on constraint
            if 'unique constraint' in error_info or 'duplicate entry' in error_info:
                 if 'vcode' in error_info and 'vname' not in error_info: raise ValueError("Gagal menyimpan. Kode fasilitas sudah digunakan.")
                 elif 'uq_facilities_vcode_vname' in error_info: raise ValueError("Gagal menyimpan. Kombinasi Kode dan Nama fasilitas sudah digunakan.")
                 else: raise ValueError("Gagal menyimpan. Data unik sudah ada.")
            else: raise ValueError("Operasi tidak dapat diselesaikan.")
        except Exception as general_error:
             db.rollback()
             # Rollback file creation
             if new_file_nid:
                 try: fileController.permanently_delete_file_record(db=db, file_id=new_file_nid)
                 except Exception as delete_db_error: print(f"CRITICAL: Failed rollback file (NID: {new_file_nid}): {delete_db_error}")
                 if saved_file_path_str and os.path.exists(saved_file_path_str):
                      try: os.remove(saved_file_path_str)
                      except Exception as del_phys_error: print(f"CRITICAL: Failed delete physical file on rollback: {del_phys_error}")
             # print(f"[User {user_id}] General Error on create. Lock released.") # Debugging lock
             raise ValueError(f"Terjadi kesalahan saat menyimpan fasilitas: {general_error}")
        # finally:
             # print(f"[User {user_id}] Exiting create lock section.") # Debugging lock

# --- Fungsi Update (Dengan Lock, Validasi Tipe & Logic Ganti File) ---
async def update_facility_with_file(
    db: Session,
    facility_vcode: str,
    facility_data: schema.FacilityUpdate,
    file: UploadFile | None,
    current_user: usersSchema.User,
    request: Request
):
    user_id = current_user.nid
    app_state = request.app.state
    lock_dict_lock = app_state.lock_dict_lock
    user_upload_locks = app_state.user_upload_locks

    async with lock_dict_lock:
        if user_id not in user_upload_locks:
            user_upload_locks[user_id] = asyncio.Lock()
        user_lock = user_upload_locks[user_id]

    # print(f"[User {user_id}] Attempting lock for update...") # Debugging lock
    async with user_lock:
        # print(f"[User {user_id}] Lock acquired for update.") # Debugging lock
        db_facility = get_facility_by_code(db, facility_code=facility_vcode)
        if not db_facility:
            if file: await file.close()
            # print(f"[User {user_id}] Facility not found. Lock released.") # Debugging lock
            return None

        old_file_nid = db_facility.nid_file
        new_file_nid = old_file_nid
        saved_file_path_str = None
        saved_file_path = None # Path object for cleanup

        if file:
            try:
                # Validasi Tipe & Ekstensi File Baru
                if file.content_type not in ALLOWED_IMAGE_TYPES:
                    raise ValueError(f"Tipe file tidak valid: {file.content_type}. Hanya gambar (jpg, png, webp) yang diizinkan.")
                file_extension = Path(file.filename).suffix
                if file_extension.lower() not in ALLOWED_IMAGE_EXTENSIONS:
                     raise ValueError(f"Ekstensi file tidak valid: {file_extension}")

                # Proses Simpan File Baru
                unique_filename = f"{uuid.uuid4()}{file_extension}"
                saved_file_path = UPLOAD_DIRECTORY / unique_filename
                saved_file_path_str = str(saved_file_path.resolve())

                with saved_file_path.open("wb") as buffer:
                    while chunk := await file.read(8192):
                         buffer.write(chunk)
                file_size_bytes = saved_file_path.stat().st_size

                # Buat Metadata File Baru
                file_metadata = filesSchema.FileCreate(
                    vcode=str(uuid.uuid4()), vname=file.filename, vtype=file.content_type,
                    vpath=saved_file_path_str, vextension=file_extension, nsize=file_size_bytes,
                    vcategory="facility", nis_public=1, vcreated_by=facility_data.vmodified_by
                )
                created_file = fileController.create_file(db=db, file_data=file_metadata)
                new_file_nid = created_file.nid

            except ValueError as ve:
                if file and not getattr(file, '_file', None) is None and not file._file.closed : await file.close()
                raise ve # Re-raise validation error
            except Exception as file_error:
                # Cleanup file fisik jika gagal
                if saved_file_path and saved_file_path.exists():
                    try: os.remove(saved_file_path)
                    except Exception as del_err: print(f"Error deleting new file on update error cleanup: {del_err}")
                if file and not getattr(file, '_file', None) is None and not file._file.closed : await file.close()
                raise ValueError(f"Gagal memproses file baru: {file_error}")
            finally:
                if file and not getattr(file, '_file', None) is None and not file._file.closed :
                    await file.close()

        # Update Data Facility
        update_data = facility_data.model_dump(exclude_unset=True, exclude={'nid_file'})
        for key, value in update_data.items():
            if hasattr(db_facility, key):
                setattr(db_facility, key, value)

        if file or 'nid_file' in facility_data.model_dump(exclude_unset=False):
             requested_nid_file = facility_data.nid_file if 'nid_file' in facility_data.model_dump(exclude_unset=False) else None
             db_facility.nid_file = new_file_nid if file else requested_nid_file

        db_facility.dsort_at = datetime.utcnow()

        try:
            db.commit()
            db.refresh(db_facility)
            db_facility = get_facility(db, db_facility.nid) # Re-fetch

            # Inaktivasi File Lama (jika ada penggantian file baru)
            if file and old_file_nid is not None and old_file_nid != new_file_nid:
                 try:
                     old_file_record = fileController.get_file(db, file_id=old_file_nid)
                     if old_file_record and old_file_record.nstatus == 1:
                          fileController.delete_file(db, file_vcode=old_file_record.vcode, modified_by=facility_data.vmodified_by)
                          print(f"[User {user_id}] Inactivated old file (NID: {old_file_nid}).")
                 except Exception as e:
                     print(f"Warning: Failed to inactivate old file (NID: {old_file_nid}): {e}")

            # print(f"[User {user_id}] Facility updated. Lock released.") # Debugging lock
            return db_facility

        except IntegrityError as e:
            db.rollback()
            # Rollback new file
            if file and new_file_nid is not None and new_file_nid != old_file_nid:
                try: fileController.permanently_delete_file_record(db=db, file_id=new_file_nid)
                except Exception as delete_new_file_error: print(f"CRITICAL: Failed rollback new file (NID: {new_file_nid}) on update error: {delete_new_file_error}")
                if saved_file_path_str and os.path.exists(saved_file_path_str):
                    try: os.remove(saved_file_path_str)
                    except Exception as del_phys_error: print(f"CRITICAL: Failed delete new physical file on update rollback: {del_phys_error}")

            error_info = str(e.orig).lower()
            # print(f"[User {user_id}] IntegrityError on update. Lock released.") # Debugging lock
            if 'unique constraint' in error_info or 'duplicate entry' in error_info:
                 if 'vcode' in error_info and 'vname' not in error_info: raise ValueError("Gagal memperbarui. Kode fasilitas yang baru sudah digunakan.")
                 elif 'uq_facilities_vcode_vname' in error_info: raise ValueError("Gagal memperbarui. Kombinasi Kode dan Nama fasilitas yang baru sudah digunakan.")
                 else: raise ValueError("Gagal memperbarui. Data unik sudah ada.")
            else: raise ValueError("Operasi tidak dapat diselesaikan.")
        except Exception as general_error:
            db.rollback()
            # Rollback new file
            if file and new_file_nid is not None and new_file_nid != old_file_nid:
                try: fileController.permanently_delete_file_record(db=db, file_id=new_file_nid)
                except Exception as delete_new_file_error: print(f"CRITICAL: Failed rollback new file (NID: {new_file_nid}) on update error: {delete_new_file_error}")
                if saved_file_path_str and os.path.exists(saved_file_path_str):
                    try: os.remove(saved_file_path_str)
                    except Exception as del_phys_error: print(f"CRITICAL: Failed delete new physical file on update rollback: {del_phys_error}")
            # print(f"[User {user_id}] General Error on update. Lock released.") # Debugging lock
            raise ValueError(f"Terjadi kesalahan saat memperbarui fasilitas: {general_error}")
        # finally:
             # print(f"[User {user_id}] Exiting update lock section.") # Debugging lock


# --- Fungsi Get List (dengan join file) ---
def get_facilities(
    db: Session, skip: int = 0, limit: int = 10, search: str | None = None,
    vname: str | None = None, vcode: str | None = None, vdesc: str | None = None,
    nstatus: int | None = None
):
    query = db.query(models.Facility).options(
        joinedload(models.Facility.related_file_relationship)
    )
    if search:
        search_filter = or_(
            models.Facility.vname.ilike(f"%{search}%"),
            models.Facility.vcode.ilike(f"%{search}%"),
            models.Facility.vdesc.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    if vname: query = query.filter(models.Facility.vname.ilike(f"%{vname}%"))
    if vcode: query = query.filter(models.Facility.vcode.ilike(f"%{vcode}%"))
    if vdesc: query = query.filter(models.Facility.vdesc.ilike(f"%{vdesc}%"))
    if nstatus is not None: query = query.filter(models.Facility.nstatus == nstatus)
    total = query.count()
    query = query.order_by(models.Facility.dsort_at.desc())
    data = query.offset(skip).limit(limit).all()
    return {"data": data, "total": total}

# --- Fungsi Delete (dengan soft delete file terkait) ---
def delete_facility(db: Session, facility_vcode: str, modified_by: str = "system"):
    db_facility = get_facility_by_code(db, facility_code=facility_vcode)
    if db_facility:
        file_to_inactivate_nid = db_facility.nid_file
        if db_facility.nstatus == 0:
             return db_facility

        db_facility.nstatus = 0
        db_facility.vmodified_by = modified_by
        db_facility.dsort_at = datetime.utcnow()
        try:
            db.commit()
            db.refresh(db_facility)
            # Soft Delete File Terkait
            if file_to_inactivate_nid:
                try:
                    related_file = fileController.get_file(db, file_id=file_to_inactivate_nid)
                    if related_file and related_file.nstatus == 1:
                        fileController.delete_file(db, file_vcode=related_file.vcode, modified_by=modified_by)
                except Exception as e:
                    print(f"Warning: Failed to soft delete associated file (NID: {file_to_inactivate_nid}): {e}")
        except Exception as e:
            db.rollback()
            raise ValueError(f"Gagal menonaktifkan fasilitas: {e}")
    return db_facility

# --- Fungsi Dropdown ---
def get_all_facilities_for_dropdown(db: Session):
    facilities = (
        db.query(models.Facility)
        .filter(models.Facility.nstatus == 1)
        .order_by(models.Facility.vname)
        .all()
    )
    return {"data": facilities}