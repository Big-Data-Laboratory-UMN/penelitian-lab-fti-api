from sqlalchemy import or_
from sqlalchemy.orm import Session
from ..models import rolesModel as models
from ..schemas import rolesSchema as schema


def get_role_by_code(db: Session, role_code: str):
    """
    Fungsi untuk mencari role berdasarkan vcode (unique).
    """
    return db.query(models.Role).filter(models.Role.vcode == role_code).first()

def create_role(db: Session, role: schema.RoleCreate):
    """
    Fungsi untuk membuat role baru.
    """
    db_role = models.Role(**role.model_dump())
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    return db_role

def update_role(db: Session, role_id: int, role: schema.RoleUpdate):
    """
    Fungsi untuk mengupdate role yang sudah ada.
    """
    db_role = get_role(db, role_id=role_id)
    if db_role:
        db_role.vname = role.vname
        db_role.vdesc = role.vdesc
        db_role.nstatus = role.nstatus
        db_role.vmodified_by = role.vmodified_by 
        
        db.commit()
        db.refresh(db_role)
    return db_role

def get_roles(
    db: Session, 
    skip: int = 0, 
    limit: int = 10, 
    search: str | None = None,
    vname: str | None = None,
    vcode: str | None = None,
    vdesc: str | None = None,
    nstatus: int | None = None
):
    """
    Mengambil data role dengan paginasi, total data, dan filter pencarian.
    """
    query = db.query(models.Role)

    if search:
        search_filter = or_(
            models.Role.vname.ilike(f"%{search}%"),
            models.Role.vcode.ilike(f"%{search}%"),
            models.Role.vdesc.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    if vname:
        query = query.filter(models.Role.vname.ilike(f"%{vname}%"))
    if vcode:
        query = query.filter(models.Role.vcode.ilike(f"%{vcode}%"))
    if vdesc:
        query = query.filter(models.Role.vdesc.ilike(f"%{vdesc}%"))
    if nstatus is not None:
        query = query.filter(models.Role.nstatus == nstatus)

    total = query.count()
    
    has_modified = db.query(models.Role).filter(models.Role.dmodified_at.isnot(None)).first()

    if has_modified:
        query = query.order_by(models.Role.dmodified_at.desc())
    else:
        query = query.order_by(models.Role.dcreated_at.desc())
    
    data = query.offset(skip).limit(limit).all()

    return {"data": data, "total": total}

def get_role(db: Session, role_id: int):
    """
    Fungsi ini cuma fokus nyari satu role berdasarkan ID-nya.
    """
    return db.query(models.Role).filter(models.Role.nid == role_id).first()

def delete_role(db: Session, role_id: int):
    """
    Melakukan soft delete dengan mengubah nstatus menjadi 0 (Inactive).
    """
    db_role = db.query(models.Role).filter(models.Role.nid == role_id).first()
    if db_role:
        db_role.nstatus = 0
        db.commit()
        db.refresh(db_role)
    return db_role


def get_all_roles_for_dropdown(db: Session):
    """
    Mengambil semua data role yang aktif (nstatus=1) untuk dropdown, 
    tanpa paginasi.
    """
    roles = db.query(models.Role).filter(models.Role.nstatus == 1).order_by(models.Role.vname).all()
    return {"data": roles}