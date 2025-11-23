from sqlalchemy import or_, update
from sqlalchemy.orm import Session
from datetime import datetime
from ..models import labContentModel as models
from ..schemas import labContentSchema as schema

import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def now_wib() -> datetime:
    return datetime.now(JAKARTA_TZ)

def get_lab_contents(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    vtitle: str | None = None,
    vcode: str | None = None,
    vsummary: str | None = None,
    vcontent: str | None = None,
    nstatus: int | None = None,
    accessible_lab_ids: list[int] | None = None
):
    query = db.query(models.LabContent)

    if search:
        search_filter = or_(
            models.LabContent.vtitle.ilike(f"%{search}%"),
            models.LabContent.vcode.ilike(f"%{search}%"),
            models.LabContent.vsummary.ilike(f"%{search}%"),
            models.LabContent.vcontent.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    # Filter by accessible labs (None means all labs for SA)
    if accessible_lab_ids is not None:
        if len(accessible_lab_ids) == 0:
            # User has no accessible labs, return empty
            return {"data": [], "total": 0}
        query = query.filter(models.LabContent.nid_lab.in_(accessible_lab_ids))

    if vcode:
        query = query.filter(models.LabContent.vcode.ilike(f"%{vcode}%"))
    if vsummary:
        query = query.filter(models.LabContent.vsummary.ilike(f"%{vsummary}%"))
    if vcontent:
        query = query.filter(models.LabContent.vcontent.ilike(f"%{vcontent}%"))
    if vtitle:
        query = query.filter(models.LabContent.vtitle.ilike(f"%{vtitle}%"))
    if nstatus is not None:
        query = query.filter(models.LabContent.nstatus == nstatus)

    total = query.count()

    # Urutkan berdasarkan waktu terakhir diubah/dibuat
    query = query.order_by(models.LabContent.dcreated_at.desc())

    data = query.offset(skip).limit(limit).all()

    return {"data": data, "total": total}


def get_lab_content_by_vcode(db: Session, vcode: str):
    return db.query(models.LabContent).filter(
        models.LabContent.vcode == vcode,
        models.LabContent.nstatus == 1
    ).first()


def get_lab_content_by_id(db: Session, nid: int):
    return db.query(models.LabContent).filter(models.LabContent.nid == nid).first()


def create_lab_content(db: Session, lc_data: schema.LabContentCreate):
    try:
        db_lc = models.LabContent(**lc_data.model_dump())
        db_lc.dcreated_at = now_wib()
        db.add(db_lc)
        db.commit()
        db.refresh(db_lc)
        return db_lc
    except Exception as e:
        db.rollback()
        raise ValueError(f"Gagal membuat lab content. {e}")


def update_lab_content(db: Session, vcode: str, lc_data: schema.LabContentUpdate):
    db_lc = get_lab_content_by_vcode(db, vcode)
    if not db_lc:
        return None

    try:
        update_data = lc_data.model_dump(exclude_unset=True)
        update_data["dmodified_at"] = now_wib()

        stmt = update(models.LabContent).where(
            models.LabContent.vcode == vcode,
            models.LabContent.nstatus == 1
        ).values(**update_data)
        db.execute(stmt)
        db.commit()
        db.refresh(db_lc)
        return db_lc
    except Exception as e:
        db.rollback()
        raise ValueError(f"Gagal mengupdate lab content. {e}")


def delete_lab_content(db: Session, vcode: str, modified_by: str):
    db_lc = get_lab_content_by_vcode(db, vcode)
    if not db_lc:
        return None

    try:
        stmt = update(models.LabContent).where(
            models.LabContent.vcode == vcode,
            models.LabContent.nstatus == 1
        ).values(
            nstatus=0,
            vmodified_by=modified_by,
            dmodified_at=now_wib()
        )
        db.execute(stmt)
        db.commit()
        return db_lc
    except Exception as e:
        db.rollback()
        raise ValueError(f"Gagal menghapus (soft delete) lab content. {e}")