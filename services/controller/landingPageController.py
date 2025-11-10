from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, update, delete
from ..models import landingPageModel as models

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
):
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
    query = query.order_by(models.LandingPages.dsort_at.desc())

    data = query.offset(skip).limit(limit).all()

    return {"data": data, "total": total}