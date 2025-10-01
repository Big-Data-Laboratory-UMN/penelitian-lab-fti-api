from sqlalchemy import or_
from sqlalchemy.orm import Session
import models, schema 

from sqlalchemy import or_
from sqlalchemy.orm import Session
import models, schema 

def get_roles(
    db: Session, 
    skip: int = 0, 
    limit: int = 10, 
    search: str | None = None,
    # Tambahkan parameter spesifik untuk filter
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

    data = query.offset(skip).limit(limit).all()

    return {"data": data, "total": total}


def get_role(db: Session, role_id: int):
    """
    Fungsi ini cuma fokus nyari satu role berdasarkan ID-nya.
    """
    return db.query(models.Role).filter(models.Role.nid == role_id).first()
