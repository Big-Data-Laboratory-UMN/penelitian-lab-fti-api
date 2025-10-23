from sqlalchemy import or_, UniqueConstraint, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import os
from ..models import filesModel as models
from ..schemas import filesSchema as schema

def get_file_by_code_and_name(db: Session, vcode: str, vname: str):
    return db.query(models.Files).filter(
        and_(
            models.Files.vcode == vcode,
            models.Files.vname == vname
        )
    ).first()

def get_file_by_code(db: Session, file_code: str):
    return db.query(models.Files).filter(models.Files.vcode == file_code).first()

def get_file(db: Session, file_id: int):
    return db.query(models.Files).filter(models.Files.nid == file_id).first()

def create_file(db: Session, file_data: schema.FileCreate):
    db_file = models.Files(**file_data.model_dump())
    db_file.dsort_at = datetime.utcnow()

    try:
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        return db_file
    except IntegrityError as e:
        db.rollback()
        error_info = str(e.orig).lower()
        print(f"IntegrityError: {error_info}")
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
            if 'vcode' in error_info and 'vname' not in error_info:
                 raise ValueError("Gagal menyimpan. Kode file sudah digunakan.")
            elif 'uq_files_vcode_vname' in error_info: # Sesuaikan jika nama constraint beda
                 raise ValueError("Gagal menyimpan. Kombinasi Kode dan Nama file sudah digunakan.")
            else:
                 raise ValueError("Gagal menyimpan. Data unik sudah ada.")
        else:
            raise ValueError("Operasi tidak dapat diselesaikan. Silakan periksa data Anda atau coba lagi.")

def update_file(db: Session, file_vcode: str, file_data: schema.FileUpdate):
    db_file = get_file_by_code(db, file_code=file_vcode)
    if not db_file:
        return None

    # Update fields from schema
    update_data = file_data.model_dump(exclude_unset=True) # Hanya update field yg ada di input
    for key, value in update_data.items():
        if hasattr(db_file, key):
            setattr(db_file, key, value)

    db_file.dsort_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(db_file)
        return db_file
    except IntegrityError as e:
        db.rollback()
        error_info = str(e.orig).lower()
        print(f"IntegrityError: {error_info}")
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
            if 'vcode' in error_info and 'vname' not in error_info:
                 raise ValueError("Gagal memperbarui. Kode file yang baru sudah digunakan.")
            elif 'uq_files_vcode_vname' in error_info:
                 raise ValueError("Gagal memperbarui. Kombinasi Kode dan Nama file yang baru sudah digunakan.")
            else:
                 raise ValueError("Gagal memperbarui. Data unik sudah ada.")
        else:
            raise ValueError("Operasi tidak dapat diselesaikan. Silakan periksa data Anda atau coba lagi.")

def get_files(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    vname: str | None = None,
    vcode: str | None = None,
    vtype: str | None = None,
    vextension: str | None = None,
    vcategory: str | None = None,
    nis_public: int | None = None,
    nstatus: int | None = None
):
    query = db.query(models.Files)

    if search:
        search_filter = or_(
            models.Files.vname.ilike(f"%{search}%"),
            models.Files.vcode.ilike(f"%{search}%"),
            models.Files.vtype.ilike(f"%{search}%"),
            models.Files.vextension.ilike(f"%{search}%"),
            models.Files.vcategory.ilike(f"%{search}%"),
        )
        query = query.filter(search_filter)

    # Specific filters
    if vname:
        query = query.filter(models.Files.vname.ilike(f"%{vname}%"))
    if vcode:
        query = query.filter(models.Files.vcode.ilike(f"%{vcode}%"))
    if vtype:
        query = query.filter(models.Files.vtype.ilike(f"%{vtype}%"))
    if vextension:
        query = query.filter(models.Files.vextension.ilike(f"%{vextension}%"))
    if vcategory:
        query = query.filter(models.Files.vcategory.ilike(f"%{vcategory}%"))
    if nis_public is not None:
        query = query.filter(models.Files.nis_public == nis_public)
    if nstatus is not None:
        query = query.filter(models.Files.nstatus == nstatus)

    total = query.count()
    query = query.order_by(models.Files.dsort_at.desc())
    data = query.offset(skip).limit(limit).all()

    return {"data": data, "total": total}

def delete_file(db: Session, file_vcode: str, modified_by: str = "system"):
    db_file = get_file_by_code(db, file_code=file_vcode)
    if db_file:
        if db_file.nstatus == 0:
             return db_file # Already inactive
        db_file.nstatus = 0
        db_file.vmodified_by = modified_by
        db_file.dsort_at = datetime.utcnow()
        try:
            db.commit()
            db.refresh(db_file)
        except Exception as e:
            db.rollback()
            print(f"Error soft deleting file {file_vcode}: {e}")
            raise ValueError(f"Gagal menonaktifkan file: {e}")
            # return None # Or raise exception
    return db_file # Return the updated object or None if not found initially

def get_all_files_for_dropdown(db: Session):
    files = (
        db.query(models.Files)
        .filter(models.Files.nstatus == 1)
        .order_by(models.Files.vname)
        .all()
    )
    return {"data": files}


def delete_physical_file_by_nid(db: Session, file_id: int) -> bool:
    """Deletes the physical file associated with a file record ID."""
    db_file = get_file(db, file_id=file_id)
    if not db_file:
        print(f"Physical file deletion failed: Record with NID {file_id} not found.")
        return False
    if not db_file.vpath:
        print(f"Physical file deletion skipped: Record with NID {file_id} has no path (vpath).")
        return False # Atau True jika dianggap berhasil karena tidak ada file

    file_path = db_file.vpath
    # Penting: Pastikan file_path ini adalah path absolut atau path relatif
    # yang benar dari direktori kerja aplikasi FastAPI Anda.
    # Jika vpath menyimpan URL cloud storage, logicnya akan berbeda (perlu library cloud).
    # Asumsi saat ini vpath adalah path di local filesystem.

    try:
        if  os.path.exists(file_path):
            os.remove(file_path)
            print(f"Successfully deleted physical file: {file_path} (NID: {file_id})")
            return True
        else:
            print(f"Physical file not found, cannot delete: {file_path} (NID: {file_id})")
            # Pertimbangkan apakah ini dianggap error atau tidak.
            # Mungkin file sudah dihapus manual sebelumnya.
            return False # Atau True jika file not found dianggap "ok"
    except PermissionError:
         print(f"Permission error deleting physical file {file_path} (NID: {file_id})")
         raise ValueError(f"Tidak ada izin untuk menghapus file: {os.path.basename(file_path)}")
    except Exception as e:
        print(f"Error deleting physical file {file_path} (NID: {file_id}): {e}")
        # Pertimbangkan logging error ini lebih detail
        raise ValueError(f"Gagal menghapus file fisik: {e}")
        # return False

# --- Fungsi untuk menghapus file fisik ---
def permanently_delete_file_record(db: Session, file_id: int) -> bool:
    """Permanently deletes the file record from the database."""
    db_file = get_file(db, file_id=file_id)
    if db_file:
        try:
            # PENTING: Panggil fungsi hapus fisik SEBELUM hapus record DB
            physical_delete_success = delete_physical_file_by_nid(db, file_id)
            # Anda bisa tentukan apakah mau lanjut hapus record jika hapus fisik gagal
            # if not physical_delete_success:
            #     print(f"Skipping permanent record deletion for NID {file_id} because physical file deletion failed or was skipped.")
            #     return False

            db.delete(db_file)
            db.commit()
            print(f"Permanently deleted file record with NID: {file_id}")
            return True
        except ValueError as ve: # Tangkap error dari delete_physical_file_by_nid
             print(f"Error during permanent deletion process for NID {file_id}: {ve}")
             # Rollback tidak diperlukan jika error terjadi sebelum db.delete
             raise ve # Lemparkan lagi errornya
        except Exception as e:
            db.rollback()
            print(f"Error permanently deleting file record NID {file_id}: {e}")
            raise ValueError(f"Gagal menghapus permanen record file: {e}")
    else:
        print(f"Permanent deletion failed: Record with NID {file_id} not found.")
        return False