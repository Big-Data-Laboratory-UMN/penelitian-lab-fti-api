from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from ..models import departmentLabModel as models
from ..models import departmentModel, labModel 
from ..schemas import departmentLabSchema as schema, usersSchema

def get_department_lab_by_code(db: Session, vcode: str):
    return db.query(models.DepartmentLab).filter(models.DepartmentLab.vcode == vcode).first()

def get_department_lab(db: Session, department_lab_id: int):
    return db.query(models.DepartmentLab).filter(models.DepartmentLab.nid == department_lab_id).first()

def create_department_lab(db: Session, department_lab: schema.DepartmentLabCreate, current_user: usersSchema.User):
    db_department_lab = models.DepartmentLab(**department_lab.model_dump())
    db_department_lab.vcreated_by = current_user.vcode
    db_department_lab.dsort_at = datetime.utcnow()

    try:
        db.add(db_department_lab)
        db.commit()
        db.refresh(db_department_lab)
        return db_department_lab
    except IntegrityError as e:
        db.rollback()
        error_info = str(e.orig).lower()
        print("IntegrityError:", error_info)
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
            if 'vcode' in error_info:
                 raise ValueError("Failed to save. The provided Code is already in use.")
            else:
                 raise ValueError("Failed to save. The provided Lab and Department combination is already in use.")
        else:
            raise ValueError("The operation could not be completed. Please review your data or refresh the page and try again.")

def update_department_lab(db: Session, department_lab_vcode: str, department_lab: schema.DepartmentLabUpdate, current_user: usersSchema.User):
    db_department_lab = get_department_lab_by_code(db, vcode=department_lab_vcode)
    if not db_department_lab:
        return None

    db_department_lab.vcode = department_lab.vcode
    db_department_lab.nid_lab = department_lab.nid_lab
    db_department_lab.nid_department = department_lab.nid_department
    db_department_lab.nstatus = department_lab.nstatus
    db_department_lab.vmodified_by = current_user.vcode
    db_department_lab.dsort_at = datetime.utcnow()

    try:
        db.add(db_department_lab)
        db.commit()
        db.refresh(db_department_lab)
        return db_department_lab
    except IntegrityError as e:
        db.rollback()
        error_info = str(e.orig).lower()
        print("IntegrityError:", error_info)
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
            if 'vcode' in error_info:
                 raise ValueError("Failed to update. The provided Code is already in use.")
            else:
                 raise ValueError("Failed to save. The provided Lab and Department combination is already in use.")
        else:
            raise ValueError("The operation could not be completed. Please review your data or refresh the page and try again.")

def get_department_labs(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    nstatus: int | None = None,
    nid_lab: int | None = None, 
    nid_department: int | None = None,
    vcode: str | None = None,
):
    query = db.query(
        models.DepartmentLab,
        labModel.Lab.vname.label("lab_name"),
        departmentModel.Department.vname.label("department_name")
    ).join(
        labModel.Lab, models.DepartmentLab.nid_lab == labModel.Lab.nid, isouter=True
    ).join(
        departmentModel.Department, models.DepartmentLab.nid_department == departmentModel.Department.nid, isouter=True
    )

    if search:
        search_filter = or_(
            models.DepartmentLab.vcode.ilike(f"%{search}%"),
            labModel.Lab.vname.ilike(f"%{search}%"),
            departmentModel.Department.vname.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
        
        
    if nstatus is not None:
        query = query.filter(models.DepartmentLab.nstatus == nstatus)
    if nid_lab is not None:
        query = query.filter(models.DepartmentLab.nid_lab == nid_lab)
    if nid_department is not None: 
        query = query.filter(models.DepartmentLab.nid_department == nid_department)
    if vcode:
        query = query.filter(models.DepartmentLab.vcode.ilike(f"%{vcode}%"))

    total = query.count()
    query = query.order_by(models.DepartmentLab.dsort_at.desc())
    
    results = query.offset(skip).limit(limit).all()
    
    data = []
    for mapping, lab_name, department_name in results:
        mapping_data = mapping.__dict__
        mapping_data['lab_name'] = lab_name or '(Name Not Found)'
        mapping_data['department_name'] = department_name or '(Name Not Found)'
        data.append(mapping_data)

    return {"data": data, "total": total}


def delete_department_lab(db: Session, department_lab_vcode: str, current_user: usersSchema.User):
    db_department_lab = get_department_lab_by_code(db, vcode=department_lab_vcode)
    if db_department_lab:
        db_department_lab.nstatus = 0
        db_department_lab.vmodified_by = current_user.vcode
        db_department_lab.dsort_at = datetime.utcnow()
        db.commit()
        db.refresh(db_department_lab)
    return db_department_lab

def get_all_department_labs_for_dropdown(db: Session):
    departmentLab = (
        db.query(models.DepartmentLab)
        .filter(models.DepartmentLab.nstatus == 1)
        .order_by(models.DepartmentLab.vcode)
        .all()
    )
    return {"data": departmentLab}

def get_labs_by_department_for_dropdown(db: Session, department_id: int):
    try:
        labs = (
            db.query(labModel.Lab.nid, labModel.Lab.vname) 
            .join(models.DepartmentLab, models.DepartmentLab.nid_lab == labModel.Lab.nid)
            .filter(
                models.DepartmentLab.nid_department == department_id,
                labModel.Lab.nstatus == 1 
            )
            .order_by(labModel.Lab.vname)
            .all()
        )
        
        # Format datanya
        formatted_labs = [{"nid": lab.nid, "vname": lab.vname} for lab in labs]
        
        return {"data": formatted_labs}

    except Exception as e:
        raise ValueError(str(e))