from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from ..models import rolesPermissionsModel as models
from ..models import rolesModel, permissionsModel # <-- IMPORT TAMBAHAN
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
    except IntegrityError as e:
        db.rollback()
        error_info = str(e.orig).lower()
        print("IntegrityError:", error_info)
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
            if 'vcode' in error_info:
                 raise ValueError("Failed to save. The provided Code is already in use.")
            else:
                 raise ValueError("Failed to save. The provided Role and Permission combination is already in use.")
        else:
            raise ValueError("The operation could not be completed. Please review your data or refresh the page and try again.")

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
    except IntegrityError as e:
        db.rollback()
        error_info = str(e.orig).lower()
        print("IntegrityError:", error_info)
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
            if 'vcode' in error_info:
                 raise ValueError("Failed to update. The provided Code is already in use.")
            else:
                 raise ValueError("Failed to save. The provided Role and Permission combination is already in use.")
        else:
            raise ValueError("The operation could not be completed. Please review your data or refresh the page and try again.")

def get_roles_permissions(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    nstatus: int | None = None,
    nid_role: int | None = None, 
    nid_permission: int | None = None,
    vcode: str | None = None,
):
    """
    Mengambil data relasi role-permission dengan paginasi, filter, dan sorting.
    """
    query = db.query(
        models.RolePermission,
        rolesModel.Role.vname.label("role_name"),
        permissionsModel.Permissions.vname.label("permission_name")
    ).join(
        rolesModel.Role, models.RolePermission.nid_role == rolesModel.Role.nid, isouter=True
    ).join(
        permissionsModel.Permissions, models.RolePermission.nid_permission == permissionsModel.Permissions.nid, isouter=True
    )

    if search:
        search_filter = or_(
            models.RolePermission.vcode.ilike(f"%{search}%"),
            rolesModel.Role.vname.ilike(f"%{search}%"),
            permissionsModel.Permissions.vname.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
        
        
    if nstatus is not None:
        query = query.filter(models.RolePermission.nstatus == nstatus)
    if nid_role is not None:
        query = query.filter(models.RolePermission.nid_role == nid_role)
    if nid_permission is not None: 
        query = query.filter(models.RolePermission.nid_permission == nid_permission)
    if vcode:
        query = query.filter(models.RolePermission.vcode.ilike(f"%{vcode}%"))

    total = query.count()
    query = query.order_by(models.RolePermission.dsort_at.desc())
    
    results = query.offset(skip).limit(limit).all()
    
    data = []
    for mapping, role_name, permission_name in results:
        mapping_data = mapping.__dict__
        mapping_data['role_name'] = role_name or '(Name Not Found)'
        mapping_data['permission_name'] = permission_name or '(Name Not Found)'
        data.append(mapping_data)

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