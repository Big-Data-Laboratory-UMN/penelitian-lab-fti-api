from sqlalchemy import or_, UniqueConstraint, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from ..models import labModel as models
from ..schemas import labSchema as schema


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


def create_lab(db: Session, lab: schema.LabCreate):
    db_lab = models.Lab(**lab.model_dump())
    db_lab.dsort_at = datetime.utcnow()

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


def update_lab(db: Session, lab_vcode: str, lab: schema.LabUpdate):
    db_lab = get_lab_by_code(db, lab_code=lab_vcode)
    if not db_lab:
        return None

    db_lab.vcode = lab.vcode
    db_lab.vname = lab.vname
    db_lab.vdesc = lab.vdesc
    db_lab.nstatus = lab.nstatus
    db_lab.vmodified_by = lab.vmodified_by
    db_lab.dsort_at = datetime.utcnow()

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
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    vname: str | None = None,
    vcode: str | None = None,
    vdesc: str | None = None,
    nstatus: int | None = None
):
    query = db.query(models.Lab)

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

    total = query.count()

    # Urutkan berdasarkan waktu terakhir diubah/dibuat
    query = query.order_by(models.Lab.dsort_at.desc())

    data = query.offset(skip).limit(limit).all()

    return {"data": data, "total": total}


def delete_lab(db: Session, lab_vcode: str):
    db_lab = db.query(models.Lab).filter(models.Lab.vcode == lab_vcode).first()
    if db_lab:
        db_lab.nstatus = 0
        db_lab.vmodified_by = "system"
        db_lab.dsort_at = datetime.utcnow()
        db.commit()
        db.refresh(db_lab)
    return db_lab


def get_all_labs_for_dropdown(db: Session):
    labs = (
        db.query(models.Lab)
        .filter(models.Lab.nstatus == 1)
        .order_by(models.Lab.vname)
        .all()
    )
    return {"data": labs}