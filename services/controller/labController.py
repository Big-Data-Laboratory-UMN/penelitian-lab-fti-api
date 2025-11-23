from sqlalchemy import or_, UniqueConstraint, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from ..models import labModel as models
from ..models import departmentLabModel, userAccessModel, rolesModel
from ..schemas import labSchema as schema, usersSchema

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


def get_lab_by_code_and_name(db: Session, vcode: str, vname: str):
    return db.query(models.Lab).filter(
        and_(
            models.Lab.vcode == vcode,
            models.Lab.vname == vname
        )
    ).first()


def get_lab_by_code(db: Session, lab_code: str):
    return db.query(models.Lab).filter(models.Lab.vcode == lab_code).first()


def get_lab(db: Session, lab_id: int):
    return db.query(models.Lab).filter(models.Lab.nid == lab_id).first()


def create_lab(db: Session, lab: schema.LabCreate, current_user: usersSchema.User):
    db_lab = models.Lab(**lab.model_dump())
    db_lab.vcreated_by = current_user.vcode
    db_lab.dsort_at = now_wib()

    try:
        db.add(db_lab)
        db.commit()
        db.refresh(db_lab)
        return db_lab
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


def update_lab(db: Session, lab_vcode: str, lab: schema.LabUpdate, current_user: usersSchema.User):
    db_lab = get_lab_by_code(db, lab_code=lab_vcode)
    if not db_lab:
        return None

    db_lab.vcode = lab.vcode
    db_lab.vname = lab.vname
    db_lab.vdesc = lab.vdesc
    db_lab.hero_image_vcode = lab.hero_image_vcode
    db_lab.ncapacity = lab.ncapacity
    db_lab.nstatus = lab.nstatus
    db_lab.vmodified_by = current_user.vcode
    db_lab.dsort_at = now_wib()

    try:
        db.commit()
        db.refresh(db_lab)
        return db_lab
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

def get_labs(
    db: Session,
    current_user: usersSchema.User, 
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    vname: str | None = None,
    vcode: str | None = None,
    vdesc: str | None = None,
    nstatus: int | None = None,
):
    # 1. LOGIC SCOPE: Cek user ini SA atau Admin Dept mana
    admin_accesses = db.query(userAccessModel.UserAccess).join(
        rolesModel.Role, userAccessModel.UserAccess.nid_role == rolesModel.Role.nid
    ).filter(
        userAccessModel.UserAccess.nid_user == current_user.nid,
        userAccessModel.UserAccess.nstatus == 1
    ).all()

    is_global = False
    allowed_dept_ids = set()

    for access in admin_accesses:
        if access.role.vcode == 'SA':
            is_global = True
            break
        elif access.role.vcode == 'ADM':
            if access.nid_department:
                allowed_dept_ids.add(access.nid_department)

    # 2. Build Base Query
    query = db.query(models.Lab)

    # 3. Apply Scope Filter (Jika bukan SA)
    if not is_global:
        if not allowed_dept_ids:
            # Admin tanpa departemen -> return kosong
            return {"data": [], "total": 0}
        
        # Join ke DepartmentLab untuk memfilter lab yang dimiliki departemen admin
        query = query.join(
            departmentLabModel.DepartmentLab,
            models.Lab.nid == departmentLabModel.DepartmentLab.nid_lab
        ).filter(
            departmentLabModel.DepartmentLab.nid_department.in_(allowed_dept_ids),
            departmentLabModel.DepartmentLab.nstatus == 1
        ).distinct() # Hindari duplikat jika lab terhubung ke multiple dept milik admin yg sama

    # 4. Filter Pencarian Standar (Existing Logic)
    if search:
        search_filter = or_(
            models.Lab.vname.ilike(f"%{search}%"),
            models.Lab.vcode.ilike(f"%{search}%"),
            models.Lab.vdesc.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    if vname:
        query = query.filter(models.Lab.vname.ilike(f"%{vname}%"))
    if vcode:
        query = query.filter(models.Lab.vcode.ilike(f"%{vcode}%"))
    if vdesc:
        query = query.filter(models.Lab.vdesc.ilike(f"%{vdesc}%"))
    if nstatus is not None:
        query = query.filter(models.Lab.nstatus == nstatus)

    # 5. Pagination & Return
    total = query.count()
    query = query.order_by(models.Lab.dsort_at.desc())
    data = query.offset(skip).limit(limit).all()

    return {"data": data, "total": total}


def delete_lab(db: Session, lab_vcode: str, current_user: usersSchema.User):
    db_lab = db.query(models.Lab).filter(models.Lab.vcode == lab_vcode).first()
    if db_lab:
        db_lab.nstatus = 0
        db_lab.vmodified_by = current_user.vcode
        db_lab.dsort_at = now_wib()
        db.commit()
        db.refresh(db_lab)
    return db_lab


def get_all_active_labs_for_dropdown(db: Session):
    labs = (
        db.query(models.Lab)
        .order_by(models.Lab.vname)
        .all()
    )
    return {"data": labs}

def get_all_labs_for_dropdown(db: Session):
    labs = (
        db.query(models.Lab)
        .filter(models.Lab.nstatus == 1)
        .order_by(models.Lab.vname)
        .all()
    )
    return {"data": labs}

def get_scoped_labs_for_dropdown(db: Session, current_user: usersSchema.User):
    """
    [SCOPED] Mengambil SEMUA lab (Active/Inactive) berdasarkan departemen Admin.
    """
    return _get_labs_by_scope_logic(db, current_user, only_active=False)

def get_scoped_active_labs_for_dropdown(db: Session, current_user: usersSchema.User):
    """
    [SCOPED] Mengambil lab AKTIF saja berdasarkan departemen Admin.
    """
    return _get_labs_by_scope_logic(db, current_user, only_active=True)


# --- Helper Internal untuk Logic Scope ---
def _get_labs_by_scope_logic(db: Session, current_user: usersSchema.User, only_active: bool):
    # 1. Cek Scope User
    admin_accesses = db.query(userAccessModel.UserAccess).join(
        rolesModel.Role, userAccessModel.UserAccess.nid_role == rolesModel.Role.nid
    ).filter(
        userAccessModel.UserAccess.nid_user == current_user.nid,
        userAccessModel.UserAccess.nstatus == 1
    ).all()

    is_global = False
    allowed_dept_ids = set()

    for access in admin_accesses:
        if access.role.vcode == 'SA':
            is_global = True
            break
        elif access.role.vcode == 'ADM':
            if access.nid_department:
                allowed_dept_ids.add(access.nid_department)

    # 2. Build Base Query
    query = db.query(models.Lab)
    if only_active:
        query = query.filter(models.Lab.nstatus == 1)

    # 3. Apply Filter Scope
    if not is_global:
        if not allowed_dept_ids:
            return {"data": []}
            
        query = query.join(
            departmentLabModel.DepartmentLab, 
            models.Lab.nid == departmentLabModel.DepartmentLab.nid_lab
        ).filter(
            departmentLabModel.DepartmentLab.nid_department.in_(allowed_dept_ids),
            departmentLabModel.DepartmentLab.nstatus == 1
        ).distinct()

    # 4. Return
    query = query.order_by(models.Lab.vname.asc())
    data = query.all()
    return {"data": data}