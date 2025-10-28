from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from ..models import labFacilityModel as models
from ..models import facilityModel, labModel 
from ..schemas import labFacilitySchema as schema

def get_facility_lab_by_code(db: Session, vcode: str):
    return db.query(models.LabFacility).filter(models.LabFacility.vcode == vcode).first()

def get_facility_lab(db: Session, facility_lab_id: int):
    return db.query(models.LabFacility).filter(models.LabFacility.nid == facility_lab_id).first()

def create_facility_lab(db: Session, facility_lab: schema.FacilityLabCreate):
    db_facility_lab = models.LabFacility(**facility_lab.model_dump())
    db_facility_lab.dsort_at = datetime.utcnow()

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
    db_facility_lab.dsort_at = datetime.utcnow()

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
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    nstatus: int | None = None,
    nid_lab: int | None = None, 
    nid_facility: int | None = None,
    vcode: str | None = None,
):
    query = db.query(
        models.LabFacility,
        labModel.Lab.vname.label("lab_name"),
        facilityModel.Facility.vname.label("facility_name")
    ).join(
        labModel.Lab, models.LabFacility.nid_lab == labModel.Lab.nid, isouter=True
    ).join(
        facilityModel.Facility, models.LabFacility.nid_facility == facilityModel.Facility.nid, isouter=True
    )

    if search:
        search_filter = or_(
            models.LabFacility.vcode.ilike(f"%{search}%"),
            labModel.Lab.vname.ilike(f"%{search}%"),
            facilityModel.Facility.vname.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
        
        
    if nstatus is not None:
        query = query.filter(models.LabFacility.nstatus == nstatus)
    if nid_lab is not None:
        query = query.filter(models.LabFacility.nid_lab == nid_lab)
    if nid_facility is not None: 
        query = query.filter(models.LabFacility.nid_facility == nid_facility)
    if vcode:
        query = query.filter(models.LabFacility.vcode.ilike(f"%{vcode}%"))

    total = query.count()
    query = query.order_by(models.LabFacility.dsort_at.desc())
    
    results = query.offset(skip).limit(limit).all()
    
    data = []
    for mapping, lab_name, facility_name in results:
        mapping_data = mapping.__dict__
        mapping_data['lab_name'] = lab_name or '(Name Not Found)'
        mapping_data['facility_name'] = facility_name or '(Name Not Found)'
        data.append(mapping_data)

    return {"data": data, "total": total}


def delete_facility_lab(db: Session, facility_lab_vcode: str, current_user: str):
    db_facility_lab = get_facility_lab_by_code(db, vcode=facility_lab_vcode)
    if db_facility_lab:
        db_facility_lab.nstatus = 0
        db_facility_lab.vmodified_by = current_user
        db_facility_lab.dsort_at = datetime.utcnow()
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