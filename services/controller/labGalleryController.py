from sqlalchemy import or_, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from ..models import labGalleryModel as models
from ..schemas import labGallerySchema as schema, usersSchema

import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")
def now_wib():
    return datetime.now(JAKARTA_TZ)

def get_gallery_by_lab_id(db: Session, lab_id: int):
    return db.query(models.LabGallery).filter(models.LabGallery.nid_lab == lab_id).all()

def get_gallery_item(db: Session, gallery_id: int):
    return db.query(models.LabGallery).filter(models.LabGallery.nid == gallery_id).first()

def get_all_gallery_items(db: Session, skip: int = 0, limit: int = 100, status: int = None, search: str = None):
    query = db.query(models.LabGallery)
    
    if status is not None:
        query = query.filter(models.LabGallery.nstatus == status)
        
    if search:
        search_term = f"%{search}%"
        query = query.join(models.LabGallery.lab).filter(
            or_(
                models.LabGallery.vcode.ilike(search_term),
                models.LabGallery.lab.property.mapper.class_.vtitle.ilike(search_term)
            )
        )
        
    total = query.count()
    data = query.offset(skip).limit(limit).all()
    
    return {"data": data, "total": total}

def create_gallery_item(db: Session, gallery: schema.LabGalleryCreate, current_user: usersSchema.User):
    db_gallery = models.LabGallery(**gallery.model_dump())
    db_gallery.vcreated_by = current_user.vcode
    
    try:
        db.add(db_gallery)
        db.commit()
        db.refresh(db_gallery)
        return db_gallery
    except IntegrityError as e:
        db.rollback()
        error_info = str(e.orig).lower()
        print("IntegrityError:", error_info)
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
             raise ValueError("Failed to save. Duplicate entry.")
        else:
            raise ValueError("The operation could not be completed.")

def update_gallery_item(db: Session, gallery_id: int, gallery: schema.LabGalleryUpdate, current_user: usersSchema.User):
    db_gallery = get_gallery_item(db, gallery_id)
    if not db_gallery:
        return None

    db_gallery.vcode = gallery.vcode
    db_gallery.nid_lab = gallery.nid_lab
    db_gallery.nid_file = gallery.nid_file
    db_gallery.nstatus = gallery.nstatus
    db_gallery.vmodified_by = current_user.vcode
    db_gallery.dmodified_at = now_wib()

    try:
        db.commit()
        db.refresh(db_gallery)
        return db_gallery
    except IntegrityError as e:
        db.rollback()
        raise ValueError(str(e))

def delete_gallery_item(db: Session, gallery_id: int, current_user: usersSchema.User):
    db_gallery = get_gallery_item(db, gallery_id)
    if db_gallery:
        db_gallery.nstatus = 0
        db_gallery.vmodified_by = current_user.vcode
        db_gallery.dmodified_at = now_wib()
        db.commit()
        db.refresh(db_gallery)
    return db_gallery
