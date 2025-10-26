# services/controller/fileController.py

# --- Import Bawaan ---
import os
import uuid
import mimetypes
import aiofiles # type: ignore
import datetime
import traceback  # <--- FIX: Tambahan untuk debugging
from pathlib import Path
from fastapi import UploadFile, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, update, delete

# --- Import Model & Skema ---
from ..models import filesModel as models
from ..schemas import filesSchema as schema, usersSchema  # <--- FIX: Tambah usersSchema

# --- Konfigurasi (dari file asli lu) ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", PROJECT_ROOT / "storage"))
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000") 

# Pastikan direktori utama ada
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# --- Fungsi Helper Internal (dari file asli lu) ---

def get_file_url(request: Request, file_path: str, is_public: bool) -> str:
    """Generate URL yang bisa diakses untuk file."""
    if is_public:
        # Hasilkan path relatif dari STORAGE_DIR
        try:
            relative_path = Path(file_path).relative_to(STORAGE_DIR).as_posix()
            # Gunakan BASE_URL dari env atau request base_url
            base_url = str(request.base_url).rstrip('/')
            return f"{base_url}/storage/{relative_path}"
        except ValueError:
            # Jika file_path tidak ada di dalam STORAGE_DIR (misal path absolut)
            return f"invalid/path/{Path(file_path).name}"
    else:
        # Untuk file private, kita butuh endpoint khusus
        # (Asumsi kita belum buat, jadi kita return path simbolis)
        return f"private/file/{Path(file_path).name}"

async def save_physical_file(file: UploadFile, category: str, request: Request, is_public: bool) -> dict:
    """
    Simpan file fisik ke disk dan kembalikan dictionary berisi metadata.
    """
    try:
        # Buat nama file unik
        original_name = Path(file.filename or "unknown.file")
        extension = original_name.suffix.lower()
        file_code = f"{uuid.uuid4()}{extension}" # Nama unik
        
        # Tentukan direktori penyimpanan
        # /app/storage/public/facilities atau /app/storage/private/facilities
        visibility = "public" if is_public else "private"
        save_dir = STORAGE_DIR / visibility / category
        save_dir.mkdir(parents=True, exist_ok=True)
        
        full_path = save_dir / file_code
        
        # Simpan file
        file_size = 0
        async with aiofiles.open(full_path, 'wb') as f:
            while chunk := await file.read(8192): # Baca per 8KB
                await f.write(chunk)
                file_size += len(chunk)

        # Dapatkan mime type
        mime_type = file.content_type or mimetypes.guess_type(original_name)[0] or "application/octet-stream"

        return {
            "file_code": file_code,
            "file_name": original_name.name,
            "full_path": str(full_path.resolve()),
            "relative_path": str(full_path.relative_to(STORAGE_DIR.parent)),
            "url": get_file_url(request, str(full_path.resolve()), is_public),
            "mime_type": mime_type,
            "extension": extension,
            "size": file_size,
            "category": category
        }
    except Exception as e:
        print(f"Gagal menyimpan file fisik: {e}")
        traceback.print_exc()
        raise IOError(f"Gagal menyimpan file: {e}")

def delete_physical_file(file_path: str):
    """Hapus file fisik dari disk."""
    try:
        path_obj = Path(file_path)
        if path_obj.exists() and path_obj.is_file():
            path_obj.unlink()
            print(f"File fisik {file_path} berhasil dihapus.")
            return True
        else:
            print(f"File fisik {file_path} tidak ditemukan untuk dihapus.")
            return False
    except Exception as e:
        print(f"Gagal menghapus file fisik {file_path}: {e}")
        traceback.print_exc()
        raise IOError(f"Gagal menghapus file fisik: {e}")


# --- FUNGSI UTAMA (UNTUK DIPANGGIL CONTROLLER LAIN) ---

async def save_file(
    db: Session,
    file: UploadFile,
    category: str,
    current_user: usersSchema.User,
    request: Request,
    is_public: bool = False
):
    """
    Fungsi helper utama untuk controller lain.
    Menyimpan file fisik DAN membuat record metadata di database.
    """
    
    # 1. Simpan file fisik
    physical_file_info = await save_physical_file(
        file=file,
        category=category,
        request=request,
        is_public=is_public
    )
    
    # 2. Siapkan data metadata
    file_metadata = schema.FileCreate(
        vcode=physical_file_info["file_code"],
        vname=physical_file_info["file_name"],
        vpath=physical_file_info["full_path"],
        vtype=physical_file_info["mime_type"],
        vextension=physical_file_info["extension"],
        nsize=physical_file_info["size"],
        vcategory=category,
        nis_public=1 if is_public else 0,
        vcreated_by=current_user.vcode
    )
    
    # 3. Simpan metadata ke DB
    try:
        db_file = create_file(db=db, file_data=file_metadata)
        return db_file
    except Exception as e:
        # Jika gagal simpan DB, hapus file fisik yang telanjur disimpan
        try:
            delete_physical_file(physical_file_info["full_path"])
        except Exception as del_e:
            print(f"CRITICAL: Gagal rollback file fisik {physical_file_info['full_path']}: {del_e}")
        # Lempar error asli (dari create_file)
        raise e


# --- CRUD STANDAR (Metadata) ---

def create_file(db: Session, file_data: schema.FileCreate):
    """Buat record metadata file di database."""
    try:
        db_file = models.Files(**file_data.model_dump())
        db_file.dcreated_at = datetime.datetime.now(datetime.timezone.utc)
        
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        return db_file
    except Exception as e:
        db.rollback()
        # --- FIX: Enhanced Debugging ---
        print("---!!! KESALAHAN DATABASE SAAT CREATE FILE !!!---")
        traceback.print_exc()
        print("-----------------------------------------------")
        raise ValueError(f"Gagal membuat record file. {e}")

def get_file(db: Session, file_id: int):
    """Ambil record file berdasarkan NID (termasuk yang soft-deleted)."""
    return db.query(models.Files).filter(models.Files.nid == file_id).first()

def get_file_by_vcode(db: Session, file_vcode: str):
    """Ambil record file berdasarkan VCODE (hanya yang aktif)."""
    return db.query(models.Files).filter(
        models.Files.vcode == file_vcode, models.Files.nstatus == 1
    ).first()

def get_files(
    db: Session, skip: int = 0, limit: int = 10, search: str | None = None,
    vname: str | None = None, vcode: str | None = None, vtype: str | None = None,
    vextension: str | None = None, vcategory: str | None = None,
    nis_public: int | None = None, nstatus: int | None = None
):
    """Ambil list record file untuk data table."""
    
    query = db.query(models.Files)
    
    # Filter status (default hanya ambil yg tidak di-soft-delete)
    if nstatus is None:
        query = query.filter(models.Files.nstatus != 0)
    elif nstatus != -1: # -1 berarti ambil semua
        query = query.filter(models.Files.nstatus == nstatus)
        
    if search:
        search_filter = or_(
            models.Files.vname.ilike(f"%{search}%"),
            models.Files.vcode.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    # Filter individual
    if vname: query = query.filter(models.Files.vname.ilike(f"%{vname}%"))
    if vcode: query = query.filter(models.Files.vcode.ilike(f"%{vcode}%"))
    if vtype: query = query.filter(models.Files.vtype.ilike(f"%{vtype}%"))
    if vextension: query = query.filter(models.Files.vextension == vextension)
    if vcategory: query = query.filter(models.Files.vcategory == vcategory)
    if nis_public is not None:
        query = query.filter(models.Files.nis_public == nis_public)

    total = query.count()
    results = query.order_by(desc(models.Files.dcreated_at)).offset(skip).limit(limit).all()
    
    return {"data": results, "total": total}

def update_file(db: Session, file_vcode: str, file_data: schema.FileUpdate):
    """Update record metadata file."""
    
    db_file = get_file_by_vcode(db, file_vcode)
    if not db_file:
        return None

    try:
        update_data = file_data.model_dump(exclude_unset=True)
        update_data['dmodified_at'] = datetime.datetime.now(datetime.timezone.utc)
        
        stmt = update(models.Files).where(
            models.Files.vcode == file_vcode,
            models.Files.nstatus == 1
        ).values(**update_data)
        
        db.execute(stmt)
        db.commit()
        db.refresh(db_file)
        return db_file
    except Exception as e:
        db.rollback()
        # --- FIX: Enhanced Debugging ---
        print("---!!! KESALAHAN DATABASE SAAT UPDATE FILE !!!---")
        traceback.print_exc()
        print("-----------------------------------------------")
        raise ValueError(f"Gagal mengupdate record file. {e}")

def delete_file(db: Session, file_vcode: str, modified_by: str):
    """Soft delete record metadata file."""
    
    db_file = get_file_by_vcode(db, file_vcode)
    if not db_file:
        return None

    try:
        stmt = update(models.Files).where(
            models.Files.vcode == file_vcode,
            models.Files.nstatus == 1
        ).values(
            nstatus=0,
            vmodified_by=modified_by,
            dmodified_at=datetime.datetime.now(datetime.timezone.utc)
        )
        db.execute(stmt)
        db.commit()
        return db_file
    except Exception as e:
        db.rollback()
        # --- FIX: Enhanced Debugging ---
        print("---!!! KESALAHAN DATABASE SAAT SOFT DELETE FILE !!!---")
        traceback.print_exc()
        print("------------------------------------------------------")
        raise ValueError(f"Gagal soft delete record file. {e}")

def permanently_delete_file_record(db: Session, file_id: int):
    """Hapus permanen record file DARI DATABASE dan HAPUS FISIK."""
    
    db_file = get_file(db, file_id) # Ambil (termasuk yg soft-deleted)
    if not db_file:
        return False # Tidak ditemukan

    file_path_to_delete = db_file.vpath
    
    try:
        # Hapus dari DB dulu
        stmt = delete(models.Files).where(models.Files.nid == file_id)
        db.execute(stmt)
        db.commit()
        
        # Jika DB berhasil, hapus file fisik
        try:
            delete_physical_file(file_path_to_delete)
        except IOError as e:
            # Gagal hapus fisik, tapi DB sudah terhapus.
            # Log error ini dengan serius!
            print(f"WARNING: Record DB file {file_id} dihapus, tapi GAGAL hapus file fisik {file_path_to_delete}. Error: {e}")
            # Jangan lempar error agar transaksi DB tetap commit

        return True
    except Exception as e:
        db.rollback()
        # --- FIX: Enhanced Debugging ---
        print("---!!! KESALAHAN DATABASE SAAT PERMANENT DELETE FILE !!!---")
        traceback.print_exc()
        print("-----------------------------------------------------------")
        raise ValueError(f"Gagal hapus permanen record file. {e}")

def get_all_files_for_dropdown(db: Session):
    """Ambil list file (hanya NID, vname) untuk dropdown."""
    
    results = db.query(
        models.Files.nid,
        models.Files.vname
    ).filter(models.Files.nstatus == 1).order_by(models.Files.vname.asc()).all()
    
    data = [
        {"value": nid, "label": vname}
        for nid, vname in results
    ]
    return {"data": data}