from sqlalchemy import or_, UniqueConstraint, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from ..models import rolesModel as models
from ..schemas import rolesSchema as schema, usersSchema

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


def get_role_by_code_and_name(db: Session, vcode: str, vname: str):
    """
    Cari role berdasarkan kombinasi vcode dan vname.
    """
    return db.query(models.Role).filter(
        and_(
            models.Role.vcode == vcode,
            models.Role.vname == vname
        )
    ).first()


def get_role_by_code(db: Session, role_code: str):
    """
    Fungsi untuk mencari role berdasarkan vcode (unique).
    """
    return db.query(models.Role).filter(models.Role.vcode == role_code).first()


def get_role(db: Session, role_id: int):
    """
    Fungsi ini cuma fokus nyari satu role berdasarkan ID-nya.
    """
    return db.query(models.Role).filter(models.Role.nid == role_id).first()


def create_role(db: Session, role: schema.RoleCreate, current_user: usersSchema.User):
    """
    Fungsi untuk membuat role baru.
    Cegah duplikasi (vcode, vname) + race condition.
    """
    db_role = models.Role(**role.model_dump())
    db_role.vcreated_by = current_user.vcode
    db_role.dsort_at = now_wib

    try:
        db.add(db_role)
        db.commit()
        db.refresh(db_role)
        return db_role
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


def update_role(db: Session, role_vcode: str, role: schema.RoleUpdate, current_user: usersSchema.User):
    """
    Fungsi untuk mengupdate role yang sudah ada berdasarkan VCODE.
    """
    db_role = get_role_by_code(db, role_code=role_vcode)
    if not db_role:
        return None

    db_role.vcode = role.vcode
    db_role.vname = role.vname
    db_role.vdesc = role.vdesc
    db_role.nstatus = role.nstatus
    db_role.vmodified_by = current_user.vcode
    db_role.dsort_at = now_wib

    try:
        db.commit()
        db.refresh(db_role)
        return db_role
    except IntegrityError as e:
        db.rollback()
        error_info = str(e.orig).lower()
        print("IntegrityError:", error_info)
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
            if 'vcode' in error_info and 'vname' not in error_info:
                 raise ValueError("Failed to update. The provided Code is already in use.")
            else:
                 raise ValueError("Failed to update. The provided Code and Name combination is already in use.")
        else:
            raise ValueError("The operation could not be completed. Please review your data or refresh the page and try again.")

def get_roles(
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
    Mengambil data role dengan paginasi, total data, dan filter pencarian.
    """
    query = db.query(models.Role)

    if search:
        search_filter = or_(
            models.Role.vname.ilike(f"%{search}%"),
            models.Role.vcode.ilike(f"%{search}%"),
            models.Role.vdesc.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    if vname:
        query = query.filter(models.Role.vname.ilike(f"%{vname}%"))
    if vcode:
        query = query.filter(models.Role.vcode.ilike(f"%{vcode}%"))
    if vdesc:
        query = query.filter(models.Role.vdesc.ilike(f"%{vdesc}%"))
    if nstatus is not None:
        query = query.filter(models.Role.nstatus == nstatus)

    total = query.count()

    # Urutkan berdasarkan waktu terakhir diubah/dibuat
    query = query.order_by(models.Role.dsort_at.desc())

    data = query.offset(skip).limit(limit).all()

    return {"data": data, "total": total}


def delete_role(db: Session, role_vcode: str, current_user: usersSchema.User):
    """
    Melakukan soft delete berdasarkan VCODE dengan mengubah nstatus menjadi 0 (Inactive).
    """
    db_role = db.query(models.Role).filter(models.Role.vcode == role_vcode).first()
    if db_role:
        db_role.nstatus = 0
        db_role.vmodified_by = current_user.vcode
        db_role.dsort_at = now_wib
        db.commit()
        db.refresh(db_role)
    return db_role


def get_all_active_roles_for_dropdown(db: Session):
    """
    Mengambil semua data role yang aktif (nstatus=1) untuk dropdown,
    tanpa paginasi.
    """
    roles = (
        db.query(models.Role)
        .filter(models.Role.nstatus == 1)
        .order_by(models.Role.vname)
        .all()
    )
    return {"data": roles}

def get_all_roles_for_dropdown(db: Session):
    """
    Mengambil semua data role yang aktif (nstatus=1) untuk dropdown,
    tanpa paginasi.
    """
    roles = (
        db.query(models.Role)
        .order_by(models.Role.vname)
        .all()
    )
    return {"data": roles}