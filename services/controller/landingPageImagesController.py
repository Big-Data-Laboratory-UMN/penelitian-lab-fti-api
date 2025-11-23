from ..models import landingPageImageModel as models
from ..schemas import landingPageImageSchema as schema
from ..schemas import usersSchema
from sqlalchemy.orm import Session
from datetime import datetime
import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def now_wib() -> datetime:
    return datetime.now(JAKARTA_TZ)

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

def create_landing_page_image(db: Session, image_data: schema.LandingPageImageCreate, current_user: usersSchema.User):
    try:
        db_image = models.LandingPageImage(**image_data.model_dump())
        db_image.vcreated_by = current_user.vcode
        db_image.dcreated_at = now_wib()
        db.add(db_image)
        db.commit()
        db.refresh(db_image)
        return db_image
    except Exception as e:
        db.rollback()
        raise ValueError(f"Gagal menambahkan gambar landing page. {e}")

def update_landing_page_image(db: Session, vcode: str, image_data: schema.LandingPageImageUpdate, current_user: usersSchema.User):
    db_image = db.query(models.LandingPageImage).filter(models.LandingPageImage.vcode == vcode).first()
    if not db_image:
        return None
    
    try:
        db_image.nid_file = image_data.nid_file
        db_image.nstatus = image_data.nstatus
        db_image.vmodified_by = current_user.vcode
        db_image.dmodified_at = now_wib()
        
        db.commit()
        db.refresh(db_image)
        return db_image
    except Exception as e:
        db.rollback()
        raise ValueError(f"Gagal mengupdate gambar landing page. {e}")