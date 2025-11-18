from ..models import landingPageImageModel as models
from sqlalchemy.orm import Session

def get_landing_page_image(
    db: Session,
    landing_page_vcode: str | None = None,
    nstatus: int | None = None,
) -> models.LandingPageImage | None:
    query = db.query(models.LandingPageImage)

    if landing_page_vcode is not None:
        query = query.filter(models.LandingPageImage.vlandingpage_image_to_landingpage_vcode == landing_page_vcode)
    if nstatus is not None:
        query = query.filter(models.LandingPageImage.nstatus == nstatus)

    if not query.first():
        return None
    return query.first()