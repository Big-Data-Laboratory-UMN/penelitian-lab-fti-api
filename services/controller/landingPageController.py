from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, update, delete
from datetime import datetime
from typing import TypedDict
from ..models import landingPageModel as models
from ..schemas import landingPageSchema as schema

import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def now_wib() -> datetime:
    return datetime.now(JAKARTA_TZ)

class LandingPageData(TypedDict):
    data: list[models.LandingPages]
    total: int

def get_landing_pages(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    vtitle: str | None = None,
    vcode: str | None = None,
    vdesc: str | None = None,
    vsection_name: str | None = None,
    nstatus: int | None = None
) -> LandingPageData:
    query = db.query(models.LandingPages)

    if search:
        search_filter = or_(
            models.LandingPages.vtitle.ilike(f"%{search}%"),
            models.LandingPages.vcode.ilike(f"%{search}%"),
            models.LandingPages.vdesc.ilike(f"%{search}%"),
            models.LandingPages.vsection_name.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    if vtitle:
        query = query.filter(models.LandingPages.vtitle.ilike(f"%{vtitle}%"))
    if vcode:
        query = query.filter(models.LandingPages.vcode.ilike(f"%{vcode}%"))
    if vdesc:
        query = query.filter(models.LandingPages.vdesc.ilike(f"%{vdesc}%"))
    if vsection_name:
        query = query.filter(models.LandingPages.vsection_name.ilike(f"%{vsection_name}%"))
    if nstatus is not None:
        query = query.filter(models.LandingPages.nstatus == nstatus)

    total = query.count()

    # Urutkan berdasarkan waktu terakhir diubah/dibuat
    query = query.order_by(models.LandingPages.vcreated_by.desc())

    data = query.offset(skip).limit(limit).all()

    return {"data": data, "total": total}


def get_landing_page_by_vcode(db: Session, vcode: str):
    return db.query(models.LandingPages).filter(
        models.LandingPages.vcode == vcode,
        models.LandingPages.nstatus == 1
    ).first()


def get_landing_page_by_id(db: Session, nid: int):
    return db.query(models.LandingPages).filter(models.LandingPages.nid == nid).first()


def create_landing_page(db: Session, lp_data: schema.LandingPageCreate):
    try:
        db_lp = models.LandingPages(**lp_data.model_dump())
        db_lp.dcreated_at = now_wib()
        db.add(db_lp)
        db.commit()
        db.refresh(db_lp)
        return db_lp
    except Exception as e:
        db.rollback()
        raise ValueError(f"Gagal membuat landing page. {e}")


def update_landing_page(db: Session, vcode: str, lp_data: schema.LandingPageUpdate):
    db_lp = get_landing_page_by_vcode(db, vcode)
    if not db_lp:
        return None

    try:
        update_data = lp_data.model_dump(exclude_unset=True)
        update_data["dmodified_at"] = now_wib()

        stmt = update(models.LandingPages).where(
            models.LandingPages.vcode == vcode,
            models.LandingPages.nstatus == 1
        ).values(**update_data)
        db.execute(stmt)
        db.commit()
        db.refresh(db_lp)
        return db_lp
    except Exception as e:
        db.rollback()
        raise ValueError(f"Gagal mengupdate landing page. {e}")


def delete_landing_page(db: Session, vcode: str, modified_by: str):
    db_lp = get_landing_page_by_vcode(db, vcode)
    if not db_lp:
        return None

    try:
        stmt = update(models.LandingPages).where(
            models.LandingPages.vcode == vcode,
            models.LandingPages.nstatus == 1
        ).values(
            nstatus=0,
            vmodified_by=modified_by,
            dmodified_at=now_wib()
        )
        db.execute(stmt)
        db.commit()
        return db_lp
    except Exception as e:
        db.rollback()
        raise ValueError(f"Gagal menghapus (soft delete) landing page. {e}")