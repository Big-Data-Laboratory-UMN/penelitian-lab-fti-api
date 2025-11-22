from fastapi import APIRouter, Depends, HTTPException, status, Response,Request, BackgroundTasks # type: ignore
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path

# Import schema dan controller yang relevan
from ..schemas import filesSchema as schema, usersSchema
from ..schemas.filesSchema import File
from ..controller import auditLogController
from ..controller import fileController, usersController, userAccessController
from ..database import SessionLocal

from datetime import datetime
import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def to_wib(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return JAKARTA_TZ.localize(dt) if dt.tzinfo is None else dt.astimezone(JAKARTA_TZ)

router = APIRouter(
    prefix="/files",
    tags=["Files"]
)

# Fungsi get_db dan check_forbidden_roles (asumsi sama)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_forbidden_roles(db: Session, current_user: usersSchema.User):
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    # Sesuaikan role yang dilarang jika perlu (misal, apakah ADM boleh?)
    if "PIC" in user_roles or "VSTR" in user_roles: # Contoh: PIC dan VSTR tidak boleh
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk operasi file ini."
        )

# --- Endpoint CRUD ---

@router.get("/", response_model=schema.FileResponse)
def read_all_files(
    skip: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    fileName: Optional[str] = None,
    fileCode: Optional[str] = None,
    fileType: Optional[str] = None,
    fileExtension: Optional[str] = None,
    fileCategory: Optional[str] = None,
    isPublic: Optional[int] = None,
    status: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user) # Terapkan role check
    files_data = fileController.get_files(
        db=db, skip=skip, limit=limit, search=search,
        vname=fileName, vcode=fileCode, vtype=fileType,
        vextension=fileExtension, vcategory=fileCategory,
        nis_public=isPublic, nstatus=status
    )
    return files_data

@router.get("/{file_id}", response_model=schema.File)
def get_file_by_id(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user) 
    file_ = fileController.get_file(db=db, file_id=file_id)
    if file_ is None:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    return file_

# Endpoint Create biasanya tidak diexpose langsung, tapi dipanggil dari controller lain
# Jika tetap mau ada endpoint create file mandiri:
@router.post("/", response_model=schema.File, status_code=status.HTTP_201_CREATED)
def create_new_file_metadata( #
    file_data: schema.FileCreate, 
    request: Request,                 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Endpoint untuk membuat metadata file (tanpa upload fisik). Upload fisik biasanya terintegrasi."""
    check_forbidden_roles(db, current_user)
    try:
        file_data.vcreated_by = current_user.vcode 
        
        # Panggil controller asli
        new_file = fileController.create_file(db=db, file_data=file_data) #
        
        # --- LOG ACTIVITY (BACKGROUND) ---
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="CREATE",
            target_model="File",
            target_identifier=new_file.vcode,
            jbefore=None,
            jafter=file_data.model_dump(),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        # ---------------------------------
        
        return new_file
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{file_vcode}", response_model=schema.File)
def update_existing_file_metadata( 
    file_vcode: str,
    file_data: schema.FileUpdate,
    request: Request,                 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Endpoint untuk mengupdate metadata file."""
    check_forbidden_roles(db, current_user)
    
    # --- AMBIL DATA SEBELUM UPDATE ---
    db_file_before = fileController.get_file_by_vcode(db, file_vcode=file_vcode) #
    if not db_file_before:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    
    # Pake mode='json' buat fix error datetime
    jbefore = File.model_validate(db_file_before).model_dump(mode='json')
    # ----------------------------------

    try:
        file_data.vmodified_by = current_user.vcode 
        
        # Panggil controller asli
        db_file = fileController.update_file(db=db, file_vcode=file_vcode, file_data=file_data) #
        
        if db_file is None: #
            raise HTTPException(status_code=404, detail="File tidak ditemukan")
        
        # --- LOG ACTIVITY (BACKGROUND) ---
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="UPDATE",
            target_model="File",
            target_identifier=db_file.vcode,
            jbefore=jbefore,
            jafter=file_data.model_dump(),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        # ---------------------------------
        
        return db_file
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{file_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_file_record( 
    file_vcode: str,
    request: Request,                 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Endpoint untuk soft delete record metadata file."""
    check_forbidden_roles(db, current_user)
    
    # --- AMBIL DATA SEBELUM DELETE ---
    db_file_before = fileController.get_file_by_vcode(db, file_vcode=file_vcode) #
    if not db_file_before:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
        
    jbefore = File.model_validate(db_file_before).model_dump(mode='json')
    # ---------------------------------
    
    # Panggil controller asli
    deleted_file = fileController.delete_file(db=db, file_vcode=file_vcode, modified_by=current_user.vcode) #
    
    if deleted_file is None: #
         raise HTTPException(status_code=404, detail="File tidak ditemukan atau gagal dihapus")

    # --- BUAT 'jafter' DARI HASIL UPDATE ---
    jafter = File.model_validate(deleted_file).model_dump(mode='json')
    # --------------------------------------

    # --- LOG ACTIVITY (BACKGROUND) ---
    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="DELETE",
        target_model="File",
        target_identifier=file_vcode,
        jbefore=jbefore, # nstatus=1
        jafter=jafter,   # nstatus=0
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    # ---------------------------------
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# Endpoint Hapus Permanen (Opsional & Hati-hati!)
@router.delete("/permanent/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def permanently_delete_file( #
    file_id: int,
    request: Request,                 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Endpoint HAPUS PERMANEN record file DAN file fisiknya (Hati-hati!)."""
    # (Role check SA Only lu udah bener di sini)
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if "SA" not in user_roles: 
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Hanya Super Admin yang boleh menghapus permanen.")

    # --- AMBIL DATA SEBELUM DELETE ---
    # Pake get_file (bukan get_file_by_vcode) biar bisa dapet file yg udah nstatus=0
    db_file_before = fileController.get_file(db=db, file_id=file_id) #
    if not db_file_before:
        raise HTTPException(status_code=404, detail="File tidak ditemukan untuk dihapus permanen.")
        
    jbefore = File.model_validate(db_file_before).model_dump(mode='json')
    file_vcode_identifier = db_file_before.vcode # Simpen vcode buat log
    # ---------------------------------

    try:
        # Panggil controller asli
        success = fileController.permanently_delete_file_record(db=db, file_id=file_id) #
        
        if not success: #
             raise HTTPException(status_code=404, detail="File tidak ditemukan untuk dihapus permanen.")
        
        # --- LOG ACTIVITY (BACKGROUND) ---
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="DELETE_PERMANENT", # Aksi khusus
            target_model="File",
            target_identifier=file_vcode_identifier, # Pake vcode yg udah disimpen
            jbefore=jbefore, # Data lengkap sebelum diapus
            jafter=None,     # Hard delete gak ada 'after'
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        # ---------------------------------
        
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as e: 
         raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
         print(f"Internal error during permanent delete file ID {file_id}: {e}")
         raise HTTPException(status_code=500, detail="Gagal menghapus file secara permanen.")


@router.get("/all-for-dropdown/", response_model=schema.FileDropdownResponse)
def read_all_files_for_dropdown(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user) # Terapkan role check
    files_data = fileController.get_all_files_for_dropdown(db=db)
    return files_data


@router.get("/{file_id}/raw")
def get_file_raw(file_id: int, db: Session = Depends(get_db)):
    """
    Serve file content for frontend preview.
    GET /files/{file_id}/raw
    """
    db_file = fileController.get_file(db=db, file_id=file_id)
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    # if db_file.vpath is absolute path, convert to Path
    file_path = Path(db_file.vpath)
    # If vpath stored relative, prefix with your UPLOAD_DIR, e.g. STORAGE_DIR / db_file.vpath
    # STORAGE_DIR = Path("/app/storage/facilities") or from config
    # file_path = STORAGE_DIR / db_file.vpath

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Physical file not found")

    return FileResponse(path=str(file_path.resolve()), media_type=db_file.vtype, filename=db_file.vname)

@router.get("/vcode/{file_vcode}/raw")
def get_file_raw_by_vcode(file_vcode: str, db: Session = Depends(get_db)):
    """
    Serve file content for frontend preview by vcode.
    GET /files/vcode/{file_vcode}/raw
    """
    db_file = fileController.get_file_by_vcode(db=db, file_vcode=file_vcode)
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = Path(db_file.vpath)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Physical file not found")

    return FileResponse(path=str(file_path.resolve()), media_type=db_file.vtype, filename=db_file.vname)