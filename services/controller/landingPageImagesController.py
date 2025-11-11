from ..models import landingPageImageModel as models
from sqlalchemy.orm import Session

def get_landing_page_image(
    db: Session,
    nid_landing_page_section: int | None = None,
    nstatus: int | None = None,
):
    query = db.query(models.LandingPageImages)

    if nid_landing_page_section is not None:
        query = query.filter(models.LandingPageImages.nid_landing_page_section == nid_landing_page_section)
    if nstatus is not None:
        query = query.filter(models.LandingPageImages.nstatus == nstatus)

    if not query.first():
        return None
    return query.first()