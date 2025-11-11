from sqlalchemy import or_, UniqueConstraint, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from ..models import labContentModel as models
from ..schemas import labContentSchema as schema

def get_lab_contents(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    vtitle: str | None = None,
    vcode: str | None = None,
    vsummary: str | None = None,
    vcontent: str | None = None,
    nstatus: int | None = None
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