from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from ..models import labFacilityModel as models
from ..models import facilityModel, labModel 
from ..schemas import labFacilitySchema as schema, usersSchema
from ..models import departmentLabModel, userAccessModel, rolesModel, labModel, facilityModel

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


def get_facility_lab_by_code(db: Session, vcode: str):
    return db.query(models.LabFacility).filter(models.LabFacility.vcode == vcode).first()

def get_facility_lab(db: Session, facility_lab_id: int):
    return db.query(models.LabFacility).filter(models.LabFacility.nid == facility_lab_id).first()

def create_facility_lab(db: Session, facility_lab: schema.FacilityLabCreate):
    db_facility_lab = models.LabFacility(**facility_lab.model_dump())
    db_facility_lab.dsort_at = now_wib()

    try:
        db.add(db_facility_lab)
        db.commit()
        db.refresh(db_facility_lab)
        return db_facility_lab
    except IntegrityError as e:
        db.rollback()
        error_info = str(e.orig).lower()
        print("IntegrityError:", error_info)
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
            if 'vcode' in error_info:
                 raise ValueError("Failed to save. The provided Code is already in use.")
            else:
                 raise ValueError("Failed to save. The provided Lab and Facility combination is already in use.")
        else:
            raise ValueError("The operation could not be completed. Please review your data or refresh the page and try again.")

def update_facility_lab(db: Session, facility_lab_vcode: str, facility_lab: schema.FacilityLabUpdate):
    db_facility_lab = get_facility_lab_by_code(db, vcode=facility_lab_vcode)
    if not db_facility_lab:
        return None

    db_facility_lab.vcode = facility_lab.vcode
    db_facility_lab.nid_lab = facility_lab.nid_lab
    db_facility_lab.nid_facility = facility_lab.nid_facility
    db_facility_lab.nstatus = facility_lab.nstatus
    db_facility_lab.vmodified_by = facility_lab.vmodified_by
    db_facility_lab.dsort_at = now_wib()

    try:
        db.add(db_facility_lab)
        db.commit()
        db.refresh(db_facility_lab)
        return db_facility_lab
    except IntegrityError as e:
        db.rollback()
        error_info = str(e.orig).lower()
        print("IntegrityError:", error_info)
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
            if 'vcode' in error_info:
                 raise ValueError("Failed to update. The provided Code is already in use.")
            else:
                 raise ValueError("Failed to save. The provided Lab and Facility combination is already in use.")
        else:
            raise ValueError("The operation could not be completed. Please review your data or refresh the page and try again.")

def get_facility_labs(
    db: Session,
    current_user: usersSchema.User, 
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    nstatus: int | None = None,
    nid_lab: int | None = None, 
    nid_facility: int | None = None,
    vcode: str | None = None,
):
    # 1. LOGIC SCOPE: Cek user ini SA atau Admin Dept mana
    admin_accesses = db.query(userAccessModel.UserAccess).join(
        rolesModel.Role, userAccessModel.UserAccess.nid_role == rolesModel.Role.nid
    ).filter(
        userAccessModel.UserAccess.nid_user == current_user.nid,
        userAccessModel.UserAccess.nstatus == 1
    ).all()

    is_global = False
    allowed_dept_ids = set()

    for access in admin_accesses:
        if access.role.vcode == 'SA':
            is_global = True
            break
        elif access.role.vcode == 'ADM':
            if access.nid_department:
                allowed_dept_ids.add(access.nid_department)

    # 2. Build Base Query
    # Kita join Lab & Facility biar bisa di-search sekalian
    query = db.query(models.LabFacility).join(
        labModel.Lab, models.LabFacility.nid_lab == labModel.Lab.nid
    ).join(
        facilityModel.Facility, models.LabFacility.nid_facility == facilityModel.Facility.nid
    )

    # 3. Apply Scope Filter (Jika bukan SA)
    if not is_global:
        if not allowed_dept_ids:
            # Admin tanpa departemen -> return kosong
            return {"data": [], "total": 0}
        
        # Join ke DepartmentLab untuk memfilter berdasarkan departemen admin
        # Path: LabFacility -> Lab -> DepartmentLab -> [Filter nid_department]
        query = query.join(
            departmentLabModel.DepartmentLab,
            labModel.Lab.nid == departmentLabModel.DepartmentLab.nid_lab
        ).filter(
            departmentLabModel.DepartmentLab.nid_department.in_(allowed_dept_ids),
            departmentLabModel.DepartmentLab.nstatus == 1
        ).distinct()

    # 4. Filter Pencarian Standar
    if search:
        search_filter = or_(
            models.LabFacility.vcode.ilike(f"%{search}%"),
            labModel.Lab.vname.ilike(f"%{search}%"),
            facilityModel.Facility.vname.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    if nid_lab is not None:
        query = query.filter(models.LabFacility.nid_lab == nid_lab)
    if nid_facility is not None:
        query = query.filter(models.LabFacility.nid_facility == nid_facility)
    if vcode:
        query = query.filter(models.LabFacility.vcode.ilike(f"%{vcode}%"))
    if nstatus is not None:
        query = query.filter(models.LabFacility.nstatus == nstatus)

    # 5. Pagination & Return
    total = query.count()
    query = query.order_by(models.LabFacility.dsort_at.desc())
    data = query.offset(skip).limit(limit).all()

    return {"data": data, "total": total}


def delete_facility_lab(db: Session, facility_lab_vcode: str, current_user: str):
    db_facility_lab = get_facility_lab_by_code(db, vcode=facility_lab_vcode)
    if db_facility_lab:
        db_facility_lab.nstatus = 0
        db_facility_lab.vmodified_by = current_user
        db_facility_lab.dsort_at = now_wib()
        db.commit()
        db.refresh(db_facility_lab)
    return db_facility_lab

def get_all_facility_labs_for_dropdown(db: Session):
    facilityLab = (
        db.query(models.LabFacility)
        .filter(models.LabFacility.nstatus == 1)
        .order_by(models.LabFacility.vcode)
        .all()
    )
    return {"data": facilityLab}


def get_facilities_by_labs_for_dropdown(db: Session, lab_id: int):
    try:
        facilities = (
            db.query(facilityModel.Facility.nid, facilityModel.Facility.vname) 
            .join(models.LabFacility, models.LabFacility.nid_facility == facilityModel.Facility.nid)
            .filter(
                models.LabFacility.nid_lab == lab_id,
                facilityModel.Facility.nstatus == 1 
            )
            .order_by(facilityModel.Facility.vname)
            .all()
        )
        
        # Format datanya
        formatted_facilities = [{"nid": facility.nid, "vname": facility.vname} for facility in facilities]
        
        return {"data": formatted_facilities}

    except Exception as e:
        raise ValueError(str(e))

def get_facilities_by_lab_code_anonymous(db: Session, lab_vcode: str):
    """
    Get all facilities associated with a lab by lab's vcode.
    Anonymous access allowed.
    Returns list of (LabFacility, Facility Name, Facility Desc, Facility File ID).
    """
    lab = db.query(labModel.Lab).filter(labModel.Lab.vcode == lab_vcode).first()
    if not lab:
        return None

    results = (
        db.query(
            models.LabFacility, 
            facilityModel.Facility.vname,
            facilityModel.Facility.vdesc,
            facilityModel.Facility.nid_file
        )
        .join(facilityModel.Facility, models.LabFacility.nid_facility == facilityModel.Facility.nid)
        .filter(
            models.LabFacility.nid_lab == lab.nid,
            models.LabFacility.nstatus == 1,
            facilityModel.Facility.nstatus == 1
        )
        .order_by(facilityModel.Facility.vname)
        .all()
    )
    return results