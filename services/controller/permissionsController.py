from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from ..models import permissionsModel as models
from ..schemas import permissionsSchema as schema

import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")
now_wib = datetime.now(JAKARTA_TZ)


# --- HELPERS ---

def to_wib(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        return JAKARTA_TZ.localize(dt)
    return dt.astimezone(JAKARTA_TZ)

def get_permission_by_code_and_name(db: Session, vcode: str, vname: str):
    """
    Cari permission berdasarkan kombinasi vcode dan vname.
    """
    return db.query(models.Permissions).filter(
        models.Permissions.vcode == vcode,
        models.Permissions.vname == vname
    ).first()


def get_permission_by_code(db: Session, permission_code: str):
    """
    Mencari permission berdasarkan vcode (unique).
    """
    return db.query(models.Permissions).filter(models.Permissions.vcode == permission_code).first()


def get_permission(db: Session, permission_id: int):
    """
    Mengambil satu permission berdasarkan ID-nya.
    """
    return db.query(models.Permissions).filter(models.Permissions.nid == permission_id).first()


def create_permission(db: Session, permission: schema.PermissionCreate):
    """
    Membuat permission baru dengan validasi unik (vcode + vname) dan anti race condition.
    """

    db_permission = models.Permissions(**permission.model_dump())
    db_permission.dsort_at = now_wib

    try:
        db.add(db_permission)
        db.commit()
        db.refresh(db_permission)
        return db_permission
    except IntegrityError as e:
        db.rollback()
        error_info = str(e.orig).lower()
        print("IntegrityError:", error_info)
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
            if 'vcode' in error_info and 'vname' not in error_info:
                raise ValueError("Failed to save. The provided Code is already in use.")
            else:
                raise ValueError("Failed to save. The provided Code and Name combination is already in use.")
        else:
            raise ValueError("The operation could not be completed. Please review your data or refresh the page and try again.")


def update_permission(db: Session, permission_vcode: str, permission: schema.PermissionUpdate):
    """
    Mengupdate permission yang sudah ada, termasuk validasi unik.
    """
    db_permission = get_permission_by_code(db, permission_code=permission_vcode)
    if not db_permission:
        return None

    db_permission.vcode = permission.vcode
    db_permission.vname = permission.vname
    db_permission.vdesc = permission.vdesc
    db_permission.nstatus = permission.nstatus
    db_permission.vmodified_by = permission.vmodified_by
    db_permission.dsort_at = now_wib

    try:
        db.add(db_permission)
        db.commit()
        db.refresh(db_permission)
        return db_permission
    except IntegrityError as e:
        db.rollback()
        error_info = str(e.orig).lower()
        print("IntegrityError:", error_info)
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
            if 'vcode' in error_info and 'vname' not in error_info:
                raise ValueError("Failed to save. The provided Code is already in use.")
            else:
                raise ValueError("Failed to save. The provided Code and Name combination is already in use.")
        else:
            raise ValueError("The operation could not be completed. Please review your data or refresh the page and try again.")


def get_permissions(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    vname: str | None = None,
    vcode: str | None = None,
    vdesc: str | None = None,
    nstatus: int | None = None
):
    """
    Mengambil data permission dengan paginasi, filter, dan sorting by waktu terbaru.
    """
    query = db.query(models.Permissions)

    if search:
        search_filter = or_(
            models.Permissions.vname.ilike(f"%{search}%"),
            models.Permissions.vcode.ilike(f"%{search}%"),
            models.Permissions.vdesc.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    if vname:
        query = query.filter(models.Permissions.vname.ilike(f"%{vname}%"))
    if vcode:
        query = query.filter(models.Permissions.vcode.ilike(f"%{vcode}%"))
    if vdesc:
        query = query.filter(models.Permissions.vdesc.ilike(f"%{vdesc}%"))
    if nstatus is not None:
        query = query.filter(models.Permissions.nstatus == nstatus)

    total = query.count()

    # Urutkan berdasarkan waktu terakhir dibuat/diubah
    query = query.order_by(models.Permissions.dsort_at.desc())

    data = query.offset(skip).limit(limit).all()

    return {"data": data, "total": total}


def delete_permission(db: Session, permission_vcode: str):
    """
    Soft delete: ubah nstatus jadi 0 (Inactive).
    """
    db_permission = db.query(models.Permissions).filter(models.Permissions.vcode == permission_vcode).first()
    if db_permission:
        db_permission.nstatus = 0
        db_permission.vmodified_by = "system"
        db_permission.dsort_at = now_wib
        db.commit()
        db.refresh(db_permission)
    return db_permission


def get_all_permissions_for_dropdown(db: Session):
    """
    Mengambil semua permission aktif (nstatus=1) tanpa paginasi, untuk dropdown.
    """
    permissions = (
        db.query(models.Permissions)
        .filter(models.Permissions.nstatus == 1)
        .order_by(models.Permissions.vname)
        .all()
    )
    return {"data": permissions}