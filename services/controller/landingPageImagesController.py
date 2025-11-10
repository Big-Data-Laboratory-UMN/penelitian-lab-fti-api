from ..models import landingPageImageModel as models
from sqlalchemy.orm import Session

def get_landing_page_images(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    nid_landing_page_section: int | None = None,
    nstatus: int | None = None
):
    query = db.query(models.LandingPageImages)

    if nid_landing_page_section is not None:
        query = query.filter(models.LandingPageImages.nid_landing_page_section == nid_landing_page_section)
    if nstatus is not None:
        query = query.filter(models.LandingPageImages.nstatus == nstatus)

    total = query.count()

    # Urutkan berdasarkan waktu terakhir diubah/dibuat
    query = query.order_by(models.LandingPageImages.dsort_at.desc())

    data = query.offset(skip).limit(limit).all()

    return {"data": data, "total": total}