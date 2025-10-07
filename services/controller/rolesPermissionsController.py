from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from ..models import rolesPermissionsModel as models
from ..schemas import rolesPermissionsSchema as schema

def get_role_permission_by_code(db: Session, vcode: str):
    """
    Mencari relasi role-permission berdasarkan vcode (unique).
    """
    return db.query(models.RolePermission).filter(models.RolePermission.vcode == vcode).first()

def get_role_permission(db: Session, role_permission_id: int):
    """
    Mengambil satu relasi role-permission berdasarkan ID-nya.
    """
    return db.query(models.RolePermission).filter(models.RolePermission.nid == role_permission_id).first()

def create_role_permission(db: Session, role_permission: schema.RolePermissionCreate):
    """
    Membuat relasi role-permission baru dengan validasi unik.
    """
    db_role_permission = models.RolePermission(**role_permission.model_dump())
    db_role_permission.dsort_at = datetime.utcnow()

    try:
        db.add(db_role_permission)
        db.commit()
        db.refresh(db_role_permission)
        return db_role_permission
    except IntegrityError:
        db.rollback()
        raise ValueError("Failed to save. The provided Role and Permission combination is already in use.")

def update_role_permission(db: Session, role_permission_vcode: str, role_permission: schema.RolePermissionUpdate):
    """
    Mengupdate relasi role-permission yang sudah ada.
    """
    db_role_permission = get_role_permission_by_code(db, vcode=role_permission_vcode)
    if not db_role_permission:
        return None

    db_role_permission.vcode = role_permission.vcode
    db_role_permission.nid_role = role_permission.nid_role
    db_role_permission.nid_permission = role_permission.nid_permission
    db_role_permission.nstatus = role_permission.nstatus
    db_role_permission.vmodified_by = role_permission.vmodified_by
    db_role_permission.dsort_at = datetime.utcnow()

    try:
        db.add(db_role_permission)
        db.commit()
        db.refresh(db_role_permission)
        return db_role_permission
    except IntegrityError:
        db.rollback()
        raise ValueError("Failed to update. The provided Role and Permission combination is already in use.")

def get_roles_permissions(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    nstatus: int | None = None
):
    """
    Mengambil data relasi role-permission dengan paginasi, filter, dan sorting.
    """
    query = db.query(models.RolePermission)

    if search:
        query = query.filter(models.RolePermission.vcode.ilike(f"%{search}%"))
    if nstatus is not None:
        query = query.filter(models.RolePermission.nstatus == nstatus)

    total = query.count()
    query = query.order_by(models.RolePermission.dsort_at.desc())
    data = query.offset(skip).limit(limit).all()

    return {"data": data, "total": total}

def delete_role_permission(db: Session, role_permission_vcode: str):
    """
    Soft delete: ubah nstatus jadi 0 (Inactive).
    """
    db_role_permission = get_role_permission_by_code(db, vcode=role_permission_vcode)
    if db_role_permission:
        db_role_permission.nstatus = 0
        db_role_permission.vmodified_by = "system"
        db_role_permission.dsort_at = datetime.utcnow()
        db.commit()
        db.refresh(db_role_permission)
    return db_role_permission

def get_all_roles_permissions_for_dropdown(db: Session):
    """
    Mengambil semua relasi role-permission aktif untuk dropdown.
    """
    permissions = (
        db.query(models.RolePermission)
        .filter(models.RolePermission.nstatus == 1)
        .order_by(models.RolePermission.vcode)
        .all()
    )
    return {"data": permissions}