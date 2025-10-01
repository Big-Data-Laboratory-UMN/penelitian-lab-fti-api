from sqlalchemy.orm import Session
import models, schema 

def get_roles(db: Session, skip: int = 0, limit: int = 100):
    """
    Fungsi ini cuma fokus ngambil data semua role dari database.
    """
    return db.query(models.Role).offset(skip).limit(limit).all()

def get_role(db: Session, role_id: int):
    """
    Fungsi ini cuma fokus nyari satu role berdasarkan ID-nya.
    """
    return db.query(models.Role).filter(models.Role.nid == role_id).first()
