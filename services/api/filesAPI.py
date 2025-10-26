from fastapi import APIRouter, Depends, HTTPException, status, Response # type: ignore
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path

# Import schema dan controller yang relevan
from ..schemas import filesSchema as schema, usersSchema
from ..controller import fileController, usersController, userAccessController
from ..database import SessionLocal

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
def create_new_file_metadata( # Nama fungsi diubah biar jelas ini hanya metadata
    file_data: schema.FileCreate, # Hanya terima metadata via JSON
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Endpoint untuk membuat metadata file (tanpa upload fisik). Upload fisik biasanya terintegrasi."""
    check_forbidden_roles(db, current_user)
    try:
        file_data.vcreated_by = current_user.vcode # Set creator
        return fileController.create_file(db=db, file_data=file_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{file_vcode}", response_model=schema.File)
def update_existing_file_metadata( # Nama fungsi diubah biar jelas ini hanya metadata
    file_vcode: str,
    file_data: schema.FileUpdate,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Endpoint untuk mengupdate metadata file."""
    check_forbidden_roles(db, current_user)
    try:
        file_data.vmodified_by = current_user.vcode # Set modifier
        db_file = fileController.update_file(db=db, file_vcode=file_vcode, file_data=file_data)
        if db_file is None:
            raise HTTPException(status_code=404, detail="File tidak ditemukan")
        return db_file
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{file_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_file_record( # Nama fungsi diubah biar jelas ini hanya record
    file_vcode: str,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Endpoint untuk soft delete record metadata file."""
    check_forbidden_roles(db, current_user)
    deleted_file = fileController.delete_file(db=db, file_vcode=file_vcode, modified_by=current_user.vcode)
    if deleted_file is None:
         raise HTTPException(status_code=404, detail="File tidak ditemukan atau gagal dihapus")
    # Jika perlu hapus fisik, bisa panggil controller di sini, tapi hati-hati
    # fileController.delete_physical_file_by_nid(db, deleted_file.nid) # Contoh
    return Response(status_code=status.HTTP_204_NO_CONTENT) # Return response kosong

# Endpoint Hapus Permanen (Opsional & Hati-hati!)
@router.delete("/permanent/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def permanently_delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Endpoint HAPUS PERMANEN record file DAN file fisiknya (Hati-hati!)."""
    # Terapkan role check yang SANGAT KETAT di sini, misal hanya Super Admin
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if "SA" not in user_roles: # Contoh: Hanya SA
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Hanya Super Admin yang boleh menghapus permanen.")

    try:
        success = fileController.permanently_delete_file_record(db=db, file_id=file_id)
        if not success:
             raise HTTPException(status_code=404, detail="File tidak ditemukan untuk dihapus permanen.")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as e: # Tangkap error dari controller (misal permission error hapus fisik)
         raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
         # Log error internal
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