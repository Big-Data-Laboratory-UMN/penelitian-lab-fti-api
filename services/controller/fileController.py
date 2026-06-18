# services/controller/fileController.py

# --- Import Bawaan ---
import os
import uuid
import mimetypes
import aiofiles # type: ignore
from datetime import datetime
import traceback
from pathlib import Path
from fastapi import UploadFile, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, update, delete
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

# --- Import Model & Skema ---
from ..models import filesModel as models
from ..schemas import filesSchema as schema, usersSchema

# --- Konfigurasi ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", PROJECT_ROOT / "storage"))
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# Pastikan direktori utama ada
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# --- KEAMANAN: Whitelist ekstensi yang diizinkan ---
# Hanya ekstensi di sini yang boleh diupload. Sesuaikan jika ada kebutuhan baru.
ALLOWED_EXTENSIONS = {
    # Dokumen
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".csv",
    # Gambar
    ".jpg", ".jpeg", ".png", ".webp",
}

# Ekstensi yang SELALU dilarang, apa pun yang terjadi (file yang bisa dieksekusi)
BLOCKED_EXTENSIONS = {
    ".php", ".php3", ".php4", ".php5", ".pht", ".phtml", ".phar",
    ".py", ".pyc", ".pyo", ".rb", ".pl", ".cgi",
    ".sh", ".bash", ".bat", ".cmd", ".ps1",
    ".exe", ".com", ".dll", ".so",
    ".js", ".mjs", ".jsp", ".asp", ".aspx", ".jspx",
    ".html", ".htm", ".svg", ".xml", ".htaccess",
}


def validate_file_extension(filename: str) -> str:
    """
    Validasi ekstensi file. Mengembalikan ekstensi (lowercase) jika aman.
    Melempar ValueError jika berbahaya atau tidak diizinkan.
    """
    extension = Path(filename or "unknown.file").suffix.lower()

    if not extension:
        raise ValueError("File tidak memiliki ekstensi. Upload ditolak demi keamanan.")

    if extension in BLOCKED_EXTENSIONS:
        raise ValueError(
            f"Ekstensi file '{extension}' dilarang demi keamanan server."
        )

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Ekstensi file '{extension}' tidak diizinkan. "
            f"Yang diperbolehkan: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    return extension


# --- Fungsi Helper Internal ---
def get_file_url(request: Request, file_path: str, is_public: bool) -> str:
    """Generate URL yang bisa diakses untuk file."""
    if is_public:
        try:
            relative_path = Path(file_path).relative_to(STORAGE_DIR).as_posix()
            base_url = str(request.base_url).rstrip('/')
            return f"{base_url}/storage/{relative_path}"
        except ValueError:
            return f"invalid/path/{Path(file_path).name}"
    else:
        return f"private/file/{Path(file_path).name}"


def to_relative_path(full_path: str) -> str:
    """
    KEAMANAN (VULN-003): Ubah path absolut server menjadi path relatif
    sebelum disimpan ke DB, supaya struktur direktori server tidak bocor.
    Contoh: /home/umnbigdata/labfti/uploads/public/labGallery/abc.jpg
            -> /uploads/public/labGallery/abc.jpg
    """
    try:
        # STORAGE_DIR.parent supaya hasilnya diawali "uploads/" (sesuai config nginx kamu)
        relative = Path(full_path).relative_to(STORAGE_DIR.parent).as_posix()
        return f"/{relative}"
    except ValueError:
        # Kalau gagal (path di luar STORAGE_DIR), kembalikan nama file saja
        return f"/uploads/{Path(full_path).name}"


def resolve_physical_path(stored_path: str) -> Path:
    """
    Kebalikan dari to_relative_path: dari path relatif yang tersimpan di DB,
    cari lokasi file fisik sebenarnya di server.
    Mendukung path lama (absolut) maupun path baru (relatif) demi kompatibilitas.
    """
    p = Path(stored_path)
    # Jika path lama (absolut) dan masih ada, pakai langsung
    if p.is_absolute() and p.exists():
        return p
    # Path relatif: gabungkan dengan STORAGE_DIR.parent
    clean = stored_path.lstrip("/")
    candidate = (STORAGE_DIR.parent / clean).resolve()

    # KEAMANAN: pastikan hasil resolve TIDAK keluar dari folder uploads
    # (mencegah path traversal seperti ../../etc/passwd)
    allowed_root = (STORAGE_DIR.parent).resolve()
    if not str(candidate).startswith(str(allowed_root)):
        raise HTTPException(status_code=400, detail="Path file tidak valid.")
    return candidate


async def save_physical_file(file: UploadFile, category: str, request: Request, is_public: bool, prefix: str | None = None) -> dict:
    """
    Simpan file fisik ke disk dan kembalikan dictionary berisi metadata.
    """
    try:
        original_name = Path(file.filename or "unknown.file")

        # --- KEAMANAN (VULN-002): Validasi ekstensi SEBELUM menyimpan ---
        extension = validate_file_extension(file.filename or "")

        unique_id = uuid.uuid4()
        if prefix:
            s_prefix = prefix.upper().strip().replace(" ", "_")
            file_code = f"{s_prefix}-{unique_id}{extension}"
        else:
            file_code = f"{unique_id}{extension}"

        visibility = "public" if is_public else "private"
        save_dir = STORAGE_DIR / visibility / category
        save_dir.mkdir(parents=True, exist_ok=True)

        full_path = save_dir / file_code

        # Simpan file
        file_size = 0
        async with aiofiles.open(full_path, 'wb') as f:
            while chunk := await file.read(8192):
                await f.write(chunk)
                file_size += len(chunk)

        mime_type = file.content_type or mimetypes.guess_type(original_name)[0] or "application/octet-stream"

        return {
            "file_code": file_code,
            "file_name": original_name.name,
            # --- KEAMANAN (VULN-003): simpan path RELATIF, bukan absolut ---
            "full_path": to_relative_path(str(full_path.resolve())),
            "relative_path": str(full_path.relative_to(STORAGE_DIR.parent)),
            "url": get_file_url(request, str(full_path.resolve()), is_public),
            "mime_type": mime_type,
            "extension": extension,
            "size": file_size,
            "category": category
        }
    except ValueError:
        # Error validasi ekstensi -> diteruskan ke pemanggil untuk jadi HTTP 400
        raise
    except Exception as e:
        print(f"Gagal menyimpan file fisik: {e}")
        traceback.print_exc()
        raise IOError(f"Gagal menyimpan file: {e}")


def delete_physical_file(file_path: str):
    """Hapus file fisik dari disk."""
    try:
        path_obj = resolve_physical_path(file_path)
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
    is_public: bool = False,
    prefix: str | None = None
):
    """
    Fungsi helper utama untuk controller lain.
    Menyimpan file fisik DAN membuat record metadata di database.
    """
    # 1. Simpan file fisik (validasi ekstensi terjadi di dalam sini)
    try:
        physical_file_info = await save_physical_file(
            file=file,
            category=category,
            request=request,
            is_public=is_public,
            prefix=prefix
        )
    except ValueError as e:
        # Ekstensi ditolak -> kembalikan HTTP 400 yang jelas ke user
        raise HTTPException(status_code=400, detail=str(e))

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
        try:
            delete_physical_file(physical_file_info["full_path"])
        except Exception as del_e:
            print(f"CRITICAL: Gagal rollback file fisik {physical_file_info['full_path']}: {del_e}")
        raise e


# --- CRUD STANDAR (Metadata) ---
def create_file(db: Session, file_data: schema.FileCreate):
    """Buat record metadata file di database."""
    try:
        db_file = models.Files(**file_data.model_dump())
        db_file.dcreated_at = now_wib()

        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        return db_file
    except Exception as e:
        db.rollback()
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

    if nstatus is None:
        query = query.filter(models.Files.nstatus != 0)
    elif nstatus != -1:
        query = query.filter(models.Files.nstatus == nstatus)

    if search:
        search_filter = or_(
            models.Files.vname.ilike(f"%{search}%"),
            models.Files.vcode.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

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
        update_data['dmodified_at'] = now_wib()

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
            dmodified_at=now_wib()
        )
        db.execute(stmt)
        db.commit()
        return db_file
    except Exception as e:
        db.rollback()
        print("---!!! KESALAHAN DATABASE SAAT SOFT DELETE FILE !!!---")
        traceback.print_exc()
        print("------------------------------------------------------")
        raise ValueError(f"Gagal soft delete record file. {e}")


def permanently_delete_file_record(db: Session, file_id: int):
    """Hapus permanen record file DARI DATABASE dan HAPUS FISIK."""
    db_file = get_file(db, file_id)
    if not db_file:
        return False

    file_path_to_delete = db_file.vpath

    try:
        stmt = delete(models.Files).where(models.Files.nid == file_id)
        db.execute(stmt)
        db.commit()

        try:
            delete_physical_file(file_path_to_delete)
        except IOError as e:
            print(f"WARNING: Record DB file {file_id} dihapus, tapi GAGAL hapus file fisik {file_path_to_delete}. Error: {e}")
        return True
    except Exception as e:
        db.rollback()
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