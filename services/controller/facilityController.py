import traceback  
from fastapi import Request, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, update, delete
from datetime import datetime

from ..schemas import facilitySchema as schema
from ..schemas import usersSchema

from ..models import facilityModel as models
from ..models import filesModel 

from . import fileController 

import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")
now_wib = datetime.now(JAKARTA_TZ)


# --- HELPERS ---

def to_wib(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        return JAKARTA_TZ.localize(dt)
    return dt.astimezone(JAKARTA_TZ)

def get_facility_by_code_and_name(db: Session, vcode: str, vname: str):
    """Cek duplikat berdasarkan vcode ATAU vname (hanya data aktif)."""
    return db.query(models.Facility).filter(
        or_(models.Facility.vcode == vcode, models.Facility.vname == vname),
    ).first()

def get_facility_by_code(db: Session, vcode: str):
    """Ambil facility berdasarkan vcode (hanya data aktif)."""
    return db.query(models.Facility).filter(
        models.Facility.vcode == vcode,
    ).first()

def get_facility(db: Session, facility_id: int):
    """Ambil facility berdasarkan NID (hanya data aktif)."""
    return db.query(models.Facility).filter(
        models.Facility.nid == facility_id, 
    ).first()

async def create_facility_with_file(
    db: Session, facility_data: schema.FacilityCreate,
    file: UploadFile | None, current_user: usersSchema.User, request: Request
):
    """Buat fasilitas baru, handle upload file jika ada."""
    
    db_facility_check = get_facility_by_code_and_name(
        db, vcode=facility_data.vcode, vname=facility_data.vname
    )
    if db_facility_check:
        raise ValueError("Kode Fasilitas atau Nama Fasilitas sudah ada.")
    
    new_file_id = None
    try:
        if file:
            saved_file_data = await fileController.save_file(
                db=db, file=file, category="facilities",
                current_user=current_user, request=request, is_public=True
            )
            new_file_id = saved_file_data.nid

        db_facility = models.Facility(
            vcode=facility_data.vcode,
            vname=facility_data.vname,
            vdesc=facility_data.vdesc,
            nid_file=new_file_id, 
            nstatus=1,
            vcreated_by=current_user.vcode,
            dcreated_at=now_wib
        )
        
        db.add(db_facility)
        db.commit()
        db.refresh(db_facility)
        return db_facility
    
    except Exception as e:
        db.rollback()
        print("---!!! KESALAHAN DATABASE SAAT CREATE FASILITAS !!!---")
        traceback.print_exc()
        print("-----------------------------------------------------")
        
        if new_file_id:
            try:
                fileController.permanently_delete_file_record(db, new_file_id)
            except Exception as del_e:
                print(f"Gagal rollback file fisik {new_file_id}: {del_e}")
        
        raise ValueError(f"Operasi tidak dapat diselesaikan. {e}")

async def update_facility_with_file(
    db: Session, facility_vcode: str, facility_data: schema.FacilityUpdate,
    file: UploadFile | None, current_user: usersSchema.User, request: Request
):
    """Update fasilitas, handle penggantian file jika ada."""
    
    db_facility = get_facility_by_code(db, facility_vcode)
    if not db_facility:
        return None 
    
    if facility_data.vname != db_facility.vname:
        check_name = db.query(models.Facility).filter(
            models.Facility.vname == facility_data.vname,
            models.Facility.nstatus != 0,
            models.Facility.vcode != facility_vcode
        ).first()
        if check_name:
            raise ValueError("Nama Fasilitas sudah digunakan oleh data lain.")
    
    old_file_id = db_facility.nid_file
    new_file_id = old_file_id 

    try:
        if file:
            saved_file_data = await fileController.save_file(
                db=db, file=file, category="facilities",
                current_user=current_user, request=request, is_public=True
            )
            new_file_id = saved_file_data.nid
        
        update_data = facility_data.model_dump(exclude_unset=True)
        update_data['vmodified_by'] = current_user.vcode
        update_data['dmodified_at'] = now_wib
        update_data['nid_file'] = new_file_id 
        
        if 'vcode' in update_data:
            del update_data['vcode'] 

        stmt = update(models.Facility).where(
            models.Facility.vcode == facility_vcode,
        ).values(**update_data)
        
        db.execute(stmt)
        db.commit()
        
        if file and old_file_id:
            try:
                fileController.permanently_delete_file_record(db, old_file_id)
            except Exception as del_e:
                print(f"Gagal menghapus file lama {old_file_id}: {del_e}")
        
        db.refresh(db_facility)
        return db_facility
    
    except Exception as e:
        db.rollback()
        print("---!!! KESALAHAN DATABASE SAAT UPDATE FASILITAS !!!---")
        traceback.print_exc()
        print("-----------------------------------------------------")

        if new_file_id != old_file_id and file:
            try:
                fileController.permanently_delete_file_record(db, new_file_id)
            except Exception as del_e:
                print(f"Gagal rollback file fisik baru {new_file_id}: {del_e}")
        
        raise ValueError(f"Operasi tidak dapat diselesaikan. {e}")

def get_facilities(
    db: Session, skip: int = 0, limit: int = 10, search: str | None = None,
    vname: str | None = None, vcode: str | None = None, vdesc: str | None = None,
    nstatus: int | None = None
):
    """Ambil list fasilitas untuk data table, SUDAH DI-JOIN dengan file."""
    
    query = db.query(
        models.Facility,
        filesModel.Files  
    ).outerjoin(
        filesModel.Files, models.Facility.nid_file == filesModel.Files.nid 
    )
    
    if search:
        search_filter = or_(
            models.Facility.vname.ilike(f"%{search}%"),
            models.Facility.vcode.ilike(f"%{search}%"),
            models.Facility.vdesc.ilike(f"%{search}%"),
            filesModel.Files.vname.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    if vname: query = query.filter(models.Facility.vname.ilike(f"%{vname}%"))
    if vcode: query = query.filter(models.Facility.vcode.ilike(f"%{vcode}%"))
    if vdesc: query = query.filter(models.Facility.vdesc.ilike(f"%{vdesc}%"))
    if nstatus is not None: query = query.filter(models.Facility.nstatus == nstatus)

    total = query.count()
    
    query = query.order_by(desc(models.Facility.dsort_at))
    
    results = query.offset(skip).limit(limit).all()

    data = []
    for facility_obj, file_obj in results:
        if file_obj:
            facility_obj.related_file = file_obj 
        else:
            facility_obj.related_file = None 
        data.append(facility_obj)

    return {"data": data, "total": total}

# --- Fungsi Delete ---
def delete_facility(db: Session, facility_vcode: str, modified_by: str):
    """Soft delete fasilitas (set nstatus = 0)."""
    
    db_facility = get_facility_by_code(db, facility_vcode)
    if not db_facility:
        return None

    try:
        stmt = update(models.Facility).where(
            models.Facility.vcode == facility_vcode,
            models.Facility.nstatus != 0
        ).values(
            nstatus=0, 
            vmodified_by=modified_by,
            dmodified_at=now_wib
        )
        db.execute(stmt)
        db.commit()
        
        return db_facility 
    except Exception as e:
        db.rollback()
        print("---!!! KESALAHAN DATABASE SAAT DELETE FASILITAS !!!---")
        traceback.print_exc()
        print("-----------------------------------------------------")
        raise ValueError(f"Gagal menghapus fasilitas. {e}")


def get_all_active_facilities_for_dropdown(db: Session):
    results = db.query(
        models.Facility.nid,
        models.Facility.vname,
        models.Facility.vcode
    ).filter(models.Facility.nstatus == 1).order_by(models.Facility.vname.asc()).all()

    data = [
        {"nid": nid, "vname": f"{vname}"}
        for nid, vname, vcode in results
    ]
    return {"data": data}


def get_all_facilities_for_dropdown(db: Session):
    results = db.query(
        models.Facility.nid,
        models.Facility.vname,
        models.Facility.vcode
    ).order_by(models.Facility.vname.asc()).all()

    data = [
        {"nid": nid, "vname": f"{vname}"}
        for nid, vname, vcode in results
    ]
    return {"data": data}
