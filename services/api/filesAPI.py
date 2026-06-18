from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, BackgroundTasks, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path
import os
import time

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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_forbidden_roles(db: Session, current_user: usersSchema.User):
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if "PIC" in user_roles or "VSTR" in user_roles:
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
    check_forbidden_roles(db, current_user)
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

@router.post("/", response_model=schema.File, status_code=status.HTTP_201_CREATED)
def create_new_file_metadata(
    file_data: schema.FileCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Endpoint untuk membuat metadata file (tanpa upload fisik)."""
    check_forbidden_roles(db, current_user)
    try:
        file_data.vcreated_by = current_user.vcode

        new_file = fileController.create_file(db=db, file_data=file_data)

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

    db_file_before = fileController.get_file_by_vcode(db, file_vcode=file_vcode)
    if not db_file_before:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")

    jbefore = File.model_validate(db_file_before).model_dump(mode='json')
    try:
        file_data.vmodified_by = current_user.vcode

        db_file = fileController.update_file(db=db, file_vcode=file_vcode, file_data=file_data)

        if db_file is None:
            raise HTTPException(status_code=404, detail="File tidak ditemukan")

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

    db_file_before = fileController.get_file_by_vcode(db, file_vcode=file_vcode)
    if not db_file_before:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")

    jbefore = File.model_validate(db_file_before).model_dump(mode='json')

    deleted_file = fileController.delete_file(db=db, file_vcode=file_vcode, modified_by=current_user.vcode)

    if deleted_file is None:
         raise HTTPException(status_code=404, detail="File tidak ditemukan atau gagal dihapus")

    jafter = File.model_validate(deleted_file).model_dump(mode='json')

    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="DELETE",
        target_model="File",
        target_identifier=file_vcode,
        jbefore=jbefore,
        jafter=jafter,
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.delete("/permanent/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def permanently_delete_file(
    file_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Endpoint HAPUS PERMANEN record file DAN file fisiknya (Hati-hati!)."""
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if "SA" not in user_roles:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Hanya Super Admin yang boleh menghapus permanen.")

    db_file_before = fileController.get_file(db=db, file_id=file_id)
    if not db_file_before:
        raise HTTPException(status_code=404, detail="File tidak ditemukan untuk dihapus permanen.")

    jbefore = File.model_validate(db_file_before).model_dump(mode='json')
    file_vcode_identifier = db_file_before.vcode

    try:
        success = fileController.permanently_delete_file_record(db=db, file_id=file_id)

        if not success:
             raise HTTPException(status_code=404, detail="File tidak ditemukan untuk dihapus permanen.")

        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="DELETE_PERMANENT",
            target_model="File",
            target_identifier=file_vcode_identifier,
            jbefore=jbefore,
            jafter=None,
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )

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
    check_forbidden_roles(db, current_user)
    files_data = fileController.get_all_files_for_dropdown(db=db)
    return files_data


# --- HELPER OTORISASI AKSES FILE (VULN-004) ---
def _authorize_file_access(db: Session, db_file, current_user: Optional[usersSchema.User]):
    """
    Aturan akses file:
    - File public (nis_public == 1): boleh diakses siapa saja (termasuk tanpa login),
      karena gambar artikel & lab memang tampil ke publik.
    - File private (nis_public != 1): wajib login DAN harus pemilik file atau admin (SA/ADM).
    """
    if db_file.nis_public == 1:
        return  # public, bebas diakses

    # File private mulai dari sini
    if current_user is None:
        raise HTTPException(status_code=401, detail="Anda harus login untuk mengakses file ini.")

    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    is_admin = "SA" in user_roles or "ADM" in user_roles
    is_owner = db_file.vcreated_by == current_user.vcode

    if not is_admin and not is_owner:
        raise HTTPException(status_code=403, detail="Anda tidak punya akses ke file ini.")


@router.api_route("/{file_id}/raw", methods=["GET", "HEAD"])
def get_file_raw(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[usersSchema.User] = Depends(usersController.get_current_active_user_optional)
):
    """
    Serve file content. File public bebas diakses; file private butuh login + otorisasi.
    GET /files/{file_id}/raw
    """
    db_file = fileController.get_file(db=db, file_id=file_id)
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    _authorize_file_access(db, db_file, current_user)

    file_path = fileController.resolve_physical_path(db_file.vpath)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Physical file not found")
    return FileResponse(path=str(file_path.resolve()), media_type=db_file.vtype, filename=db_file.vname)


@router.get("/vcode/{file_vcode}/raw")
def get_file_raw_by_vcode(
    file_vcode: str,
    db: Session = Depends(get_db),
    current_user: Optional[usersSchema.User] = Depends(usersController.get_current_active_user_optional)
):
    """
    Serve file content by vcode. File public bebas diakses; file private butuh otorisasi.
    GET /files/vcode/{file_vcode}/raw
    """
    db_file = fileController.get_file_by_vcode(db=db, file_vcode=file_vcode)
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    _authorize_file_access(db, db_file, current_user)

    file_path = fileController.resolve_physical_path(db_file.vpath)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Physical file not found")
    return FileResponse(path=str(file_path.resolve()), media_type=db_file.vtype, filename=db_file.vname)