import traceback  
from fastapi import Request, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, update, delete
from datetime import datetime

from ..schemas import facilitySchema as schema
from ..schemas import usersSchema

from ..models import facilityModel as models
from ..models import filesModel 

from ..models import userAccessModel, rolesModel, labFacilityModel, departmentLabModel, labModel

from . import fileController 

import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")
def now_wib():
    return datetime.now(JAKARTA_TZ)


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
            dcreated_at=now_wib()
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
        update_data['dmodified_at'] = now_wib()
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
    db: Session,
    current_user: usersSchema.User,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    vname: str | None = None,
    vcode: str | None = None,
    vdesc: str | None = None,
    nstatus: int | None = None,
):
    # 1. LOGIC SCOPE (Cek Admin/SA)
    admin_accesses = db.query(userAccessModel.UserAccess).join(
        rolesModel.Role, userAccessModel.UserAccess.nid_role == rolesModel.Role.nid
    ).filter(
        userAccessModel.UserAccess.nid_user == current_user.nid,
        userAccessModel.UserAccess.nstatus == 1
    ).all()

    is_global = False
    allowed_dept_ids = set()
    allowed_lab_ids = set()

    for access in admin_accesses:
        if access.role.vcode == 'SA':
            is_global = True
            break
        elif access.role.vcode == 'ADM':
            if access.nid_department:
                allowed_dept_ids.add(access.nid_department)
        elif access.role.vcode == 'PIC':
            if access.nid_lab:
                allowed_lab_ids.add(access.nid_lab)

    # 2. Build Base Query (SELECT Facility DAN Files)
    # Kita select dua-duanya biar bisa di-unpacking nanti (facility_obj, file_obj)
    query = db.query(models.Facility, filesModel.Files).outerjoin(
        filesModel.Files, models.Facility.nid_file == filesModel.Files.nid
    )

    # 3. Apply Scope Filter
    if not is_global:
        if not allowed_dept_ids and not allowed_lab_ids:
            return {"data": [], "total": 0}
        
        # Join ke relasi Lab -> Dept buat filter
        query = query.join(
            labFacilityModel.LabFacility,
            models.Facility.nid == labFacilityModel.LabFacility.nid_facility
        ).join(
            labModel.Lab,
            labFacilityModel.LabFacility.nid_lab == labModel.Lab.nid
        ).join(
            departmentLabModel.DepartmentLab,
            labModel.Lab.nid == departmentLabModel.DepartmentLab.nid_lab
        )

        # Build Scope Conditions (Dept OR Lab)
        scope_conditions = []
        if allowed_dept_ids:
            scope_conditions.append(departmentLabModel.DepartmentLab.nid_department.in_(allowed_dept_ids))
        if allowed_lab_ids:
            scope_conditions.append(labModel.Lab.nid.in_(allowed_lab_ids))
        
        query = query.filter(or_(*scope_conditions))

        # Filter status relasi
        query = query.filter(
            departmentLabModel.DepartmentLab.nstatus == 1,
            labFacilityModel.LabFacility.nstatus == 1
        ).distinct()

    # 4. Filter Pencarian
    if search:
        search_filter = or_(
            models.Facility.vname.ilike(f"%{search}%"),
            models.Facility.vcode.ilike(f"%{search}%"),
            models.Facility.vdesc.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    if vname:
        query = query.filter(models.Facility.vname.ilike(f"%{vname}%"))
    if vcode:
        query = query.filter(models.Facility.vcode.ilike(f"%{vcode}%"))
    if vdesc:
        query = query.filter(models.Facility.vdesc.ilike(f"%{vdesc}%"))
    if nstatus is not None:
        query = query.filter(models.Facility.nstatus == nstatus)

    # 5. Pagination & Formatting
    total = query.count()
    query = query.order_by(models.Facility.dsort_at.desc())
    results = query.offset(skip).limit(limit).all()

    # --- [INI LOGIC YANG KEMARIN HILANG] ---
    data = []
    for facility_obj, file_obj in results:
        # Manual mapping biar Schema Pydantic seneng
        if file_obj:
            facility_obj.related_file = file_obj 
        else:
            facility_obj.related_file = None 
        data.append(facility_obj)
    # ---------------------------------------

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
            dmodified_at=now_wib()
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

def get_facility_by_code_anonymous_restricted(db: Session, facility_vcode: str):
    """
    Get facility by vcode anonymously, but ONLY if it is part of a lab (exists in LabFacility).
    """
    # Check if facility exists and is active
    facility = db.query(models.Facility).filter(
        models.Facility.vcode == facility_vcode,
        models.Facility.nstatus == 1
    ).first()

    if not facility:
        return None

    # Check if facility is linked to any active lab facility record
    is_linked = db.query(labFacilityModel.LabFacility).filter(
        labFacilityModel.LabFacility.nid_facility == facility.nid,
        labFacilityModel.LabFacility.nstatus == 1
    ).first()

    if not is_linked:
        return None # Or raise specific error if needed, but returning None implies not found/not accessible

    # If linked, return facility with file info (similar to get_facilities logic)
    # We need to fetch file info manually or use relationship if lazy='joined' isn't enough or we want specific structure
    # The model has `related_file_relationship` with lazy='joined', so `facility.related_file_relationship` should be available.
    # However, the schema expects `related_file`. Let's map it.
    
    if facility.related_file_relationship:
        facility.related_file = facility.related_file_relationship
    else:
        facility.related_file = None

    return facility

def get_scoped_facilities_for_dropdown(db: Session, current_user: usersSchema.User):
    """
    [SCOPED] Mengambil SEMUA Facility (Active/Inactive) sesuai Scope Admin.
    """
    return _get_facilities_by_scope_logic(db, current_user, only_active=False)

def get_scoped_active_facilities_for_dropdown(db: Session, current_user: usersSchema.User):
    """
    [SCOPED] Mengambil Facility AKTIF saja sesuai Scope Admin.
    """
    return _get_facilities_by_scope_logic(db, current_user, only_active=True)


# --- Helper Internal Logic ---
def _get_facilities_by_scope_logic(db: Session, current_user: usersSchema.User, only_active: bool):
    # 1. Cek Scope User
    admin_accesses = db.query(userAccessModel.UserAccess).join(
        rolesModel.Role, userAccessModel.UserAccess.nid_role == rolesModel.Role.nid
    ).filter(
        userAccessModel.UserAccess.nid_user == current_user.nid,
        userAccessModel.UserAccess.nstatus == 1
    ).all()

    is_global = False
    allowed_dept_ids = set()
    allowed_lab_ids = set()

    for access in admin_accesses:
        if access.role.vcode == 'SA':
            is_global = True
            break
        elif access.role.vcode == 'ADM':
            if access.nid_department:
                allowed_dept_ids.add(access.nid_department)
        elif access.role.vcode == 'PIC':
            if access.nid_lab:
                allowed_lab_ids.add(access.nid_lab)

    # 2. Build Base Query (Select specific columns for dropdown)
    query = db.query(
        models.Facility.nid,
        models.Facility.vname,
        models.Facility.vcode
    )
    
    if only_active:
        query = query.filter(models.Facility.nstatus == 1)

    # 3. Apply Filter Scope (Jika BUKAN SA)
    if not is_global:
        if not allowed_dept_ids and not allowed_lab_ids:
            # Admin tanpa departemen/lab = return kosong
            return {"data": []}

        # Join Berantai: Facility -> LabFacility -> Lab -> DepartmentLab
        query = query.join(
            labFacilityModel.LabFacility,
            models.Facility.nid == labFacilityModel.LabFacility.nid_facility
        ).join(
            labModel.Lab,
            labFacilityModel.LabFacility.nid_lab == labModel.Lab.nid
        ).join(
            departmentLabModel.DepartmentLab,
            labModel.Lab.nid == departmentLabModel.DepartmentLab.nid_lab
        )

        scope_conditions = []
        if allowed_dept_ids:
            scope_conditions.append(departmentLabModel.DepartmentLab.nid_department.in_(allowed_dept_ids))
        if allowed_lab_ids:
            scope_conditions.append(labModel.Lab.nid.in_(allowed_lab_ids))
        
        query = query.filter(or_(*scope_conditions))

        query = query.filter(
            departmentLabModel.DepartmentLab.nstatus == 1,
            labFacilityModel.LabFacility.nstatus == 1
        ).distinct()

    # 4. Order & Return
    query = query.order_by(models.Facility.vname.asc())
    results = query.all()
    
    # Format data sesuai schema dropdown
    data = [
        {"nid": nid, "vname": vname, "vcode": vcode}
        for nid, vname, vcode in results
    ]
    
    return {"data": data}