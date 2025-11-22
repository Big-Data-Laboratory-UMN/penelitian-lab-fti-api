from sqlalchemy import or_, UniqueConstraint, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from ..models import departmentModel as models
from ..schemas import departmentSchema as schema, usersSchema

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


def get_department_by_code_and_name(db: Session, vcode: str, vname: str):
    return db.query(models.Department).filter(
        and_(
            models.Department.vcode == vcode,
            models.Department.vname == vname
        )
    ).first()


def get_department_by_code(db: Session, department_code: str):
    return db.query(models.Department).filter(models.Department.vcode == department_code).first()


def get_department(db: Session, department_id: int):
    return db.query(models.Department).filter(models.Department.nid == department_id).first()


def create_department(db: Session, department: schema.DepartmentCreate, current_user: usersSchema.User):
    db_department = models.Department(**department.model_dump())
    db_department.vcreated_by = current_user.vcode
    db_department.dsort_at = now_wib()

    try:
        db.add(db_department)
        db.commit()
        db.refresh(db_department)
        return db_department
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


def update_department(db: Session, department_vcode: str, department: schema.DepartmentUpdate, current_user: usersSchema.User):
    db_department = get_department_by_code(db, department_code=department_vcode)
    if not db_department:
        return None

    db_department.vcode = department.vcode
    db_department.vname = department.vname
    db_department.vdesc = department.vdesc
    db_department.nstatus = department.nstatus
    db_department.vmodified_by = current_user.vcode
    db_department.dsort_at = now_wib()

    try:
        db.commit()
        db.refresh(db_department)
        return db_department
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

def get_departments(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    vname: str | None = None,
    vcode: str | None = None,
    vdesc: str | None = None,
    nstatus: int | None = None
):
    query = db.query(models.Department)

    if search:
        search_filter = or_(
            models.Department.vname.ilike(f"%{search}%"),
            models.Department.vcode.ilike(f"%{search}%"),
            models.Department.vdesc.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    if vname:
        query = query.filter(models.Department.vname.ilike(f"%{vname}%"))
    if vcode:
        query = query.filter(models.Department.vcode.ilike(f"%{vcode}%"))
    if vdesc:
        query = query.filter(models.Department.vdesc.ilike(f"%{vdesc}%"))
    if nstatus is not None:
        query = query.filter(models.Department.nstatus == nstatus)

    total = query.count()

    # Urutkan berdasarkan waktu terakhir diubah/dibuat
    query = query.order_by(models.Department.dsort_at.desc())

    data = query.offset(skip).limit(limit).all()

    return {"data": data, "total": total}


def delete_department(db: Session, department_vcode: str, current_user: usersSchema.User):
    db_department = db.query(models.Department).filter(models.Department.vcode == department_vcode).first()
    if db_department:
        db_department.nstatus = 0
        db_department.vmodified_by = current_user.vcode
        db_department.dsort_at = now_wib()
        db.commit()
        db.refresh(db_department)
    return db_department
    
def get_all_active_departments_for_dropdown(db: Session, for_user: bool = False):
    if for_user:
        departments = (
            db.query(models.Department)
            .filter(models.Department.nstatus == 1, ~models.Department.vname.ilike('%fakultas%'))
            .order_by(models.Department.vname)
            .all()
        )
    else:
        departments = (
            db.query(models.Department)
            .filter(models.Department.nstatus == 1)
            .order_by(models.Department.vname)
            .all()
        )
    return {"data": departments}

def get_all_departments_for_dropdown(db: Session):
    departments = (
        db.query(models.Department)
        .order_by(models.Department.vname)
        .all()
    )
    return {"data": departments}