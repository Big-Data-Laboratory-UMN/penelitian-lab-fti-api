from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from ..models import userAccessModel as models
from ..models import rolesModel, usersModel, departmentModel, labModel 
from ..schemas import userAccessSchema as schema

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

def get_user_access_by_code(db: Session, vcode: str):
    return db.query(models.UserAccess).filter(models.UserAccess.vcode == vcode).first()

def get_user_access(db: Session, user_access_id: int):
    return db.query(models.UserAccess).filter(models.UserAccess.nid == user_access_id).first()

def create_user_access(db: Session, user_access: schema.UserAccessCreate):

    existing_user_assignment = db.query(models.UserAccess).filter(
        models.UserAccess.nid_user == user_access.nid_user,
        models.UserAccess.nid_role == user_access.nid_role,
        models.UserAccess.nid_department == user_access.nid_department,
        models.UserAccess.nid_lab == user_access.nid_lab,
    ).first()
    
    if existing_user_assignment:
        raise ValueError("Failed to save. This exact access assignment (User, Role, Dept, Lab) already exists.")
    
    db_user_access = models.UserAccess(**user_access.model_dump())
    db_user_access.dsort_at = now_wib()

    try:
        db.add(db_user_access)
        db.commit()
        db.refresh(db_user_access)
        return db_user_access
    except IntegrityError as e:
        db.rollback()
        error_info = str(e.orig).lower()
        print("IntegrityError:", error_info)
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
            if 'vcode' in error_info:
                 raise ValueError("Failed to save. The provided Code is already in use.")
            else:
                 raise ValueError("Failed to save. The provided user access combination is already in use.")
        else:
            raise ValueError("The operation could not be completed. Please review your data or refresh the page and try again.")

def update_user_access(db: Session, user_access_vcode: str, user_access: schema.UserAccessUpdate):
    db_user_access = get_user_access_by_code(db, vcode=user_access_vcode)
    if not db_user_access:
        return None

    existing_user_assignment = db.query(models.UserAccess).filter(
        models.UserAccess.nid_user == user_access.nid_user,
        models.UserAccess.nid_role == user_access.nid_role,
        models.UserAccess.nid_department == user_access.nid_department,
        models.UserAccess.nid_lab == user_access.nid_lab,
        models.UserAccess.nid != db_user_access.nid 
    ).first()
    
    if existing_user_assignment:
        raise ValueError("Failed to update. This exact access assignment (User, Role, Dept, Lab) already exists for another record.")

    db_user_access.vcode = user_access.vcode
    db_user_access.nid_role = user_access.nid_role
    db_user_access.nid_user = user_access.nid_user
    db_user_access.nid_department = user_access.nid_department
    db_user_access.nid_lab = user_access.nid_lab 
    db_user_access.nstatus = user_access.nstatus
    db_user_access.vmodified_by = user_access.vmodified_by
    db_user_access.dsort_at = now_wib()

    try:
        db.add(db_user_access)
        db.commit()
        db.refresh(db_user_access)
        return db_user_access
    except IntegrityError as e:
        db.rollback()
        error_info = str(e.orig).lower()
        print("IntegrityError:", error_info)
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
            if 'vcode' in error_info:
                 raise ValueError("Failed to update. The provided Code is already in use.")
            else:
                 raise ValueError("Failed to save. The provided user access combination is already in use.")
        else:
            raise ValueError("The operation could not be completed. Please review your data or refresh the page and try again.")

def get_user_access(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    nstatus: int | None = None,
    nid_role: int | None = None, 
    nid_user: int | None = None,
    nid_department: int | None = None,
    nid_lab: int | None = None, 
    vcode: str | None = None,
):
    query = db.query(
        models.UserAccess,
        rolesModel.Role.vname.label("role_name"),
        usersModel.User.vname.label("user_name"),
        departmentModel.Department.vname.label("department_name"),
        labModel.Lab.vname.label("lab_name") 
    ).join(
        rolesModel.Role, models.UserAccess.nid_role == rolesModel.Role.nid, isouter=True
    ).join(
        usersModel.User, models.UserAccess.nid_user == usersModel.User.nid, isouter=True
    ).join(
        departmentModel.Department, models.UserAccess.nid_department == departmentModel.Department.nid, isouter=True
    ).join(
        labModel.Lab, models.UserAccess.nid_lab == labModel.Lab.nid, isouter=True 
    )
    if search:
        search_filter = or_(
            models.UserAccess.vcode.ilike(f"%{search}%"),
            rolesModel.Role.vname.ilike(f"%{search}%"),
            usersModel.User.vname.ilike(f"%{search}%"),
            departmentModel.Department.vname.ilike(f"%{search}%"),
            labModel.Lab.vname.ilike(f"%{search}%") 
        )
        query = query.filter(search_filter)
        
        
    if nstatus is not None:
        query = query.filter(models.UserAccess.nstatus == nstatus)
    if nid_role is not None:
        query = query.filter(models.UserAccess.nid_role == nid_role)
    if nid_user is not None: 
        query = query.filter(models.UserAccess.nid_user == nid_user)
    if nid_department is not None: 
        query = query.filter(models.UserAccess.nid_department == nid_department)
    if nid_lab is not None: # [NEW] Filter by lab
        query = query.filter(models.UserAccess.nid_lab == nid_lab)
    if vcode:
        query = query.filter(models.UserAccess.vcode.ilike(f"%{vcode}%"))

    total = query.count()
    query = query.order_by(models.UserAccess.dsort_at.desc())
    
    results = query.offset(skip).limit(limit).all()
    
    data = []
    for mapping, role_name, user_name, department_name, lab_name in results:
        mapping_data = mapping.__dict__
        mapping_data['role_name'] = role_name or '(Name Not Found)'
        mapping_data['user_name'] = user_name or '(Name Not Found)'
        mapping_data['department_name'] = department_name or '(Name Not Found)'
        mapping_data['lab_name'] = lab_name or '(N/A)' 
        data.append(mapping_data)

    return {"data": data, "total": total}


def delete_user_access(db: Session, user_access_vcode: str, current_user: str):
    db_user_access = get_user_access_by_code(db, vcode=user_access_vcode)
    if db_user_access:
        db_user_access.nstatus = 0
        db_user_access.vmodified_by = current_user
        db_user_access.dsort_at = now_wib()
        db.commit()
        db.refresh(db_user_access)
    return db_user_access

def get_all_user_access_for_dropdown(db: Session):
    user_access = (
        db.query(models.UserAccess)
        .filter(models.UserAccess.nstatus == 1)
        .order_by(models.UserAccess.vcode)
        .all()
    )
    return {"data": user_access}

def get_user_roles_by_user_id(db: Session, user_id: int) -> list[str]:
    user_access_list = (
        db.query(models.UserAccess.nid_role, rolesModel.Role.vcode)
        .join(rolesModel.Role, models.UserAccess.nid_role == rolesModel.Role.nid)
        .filter(
            models.UserAccess.nid_user == user_id,
            models.UserAccess.nstatus == 1, 
            rolesModel.Role.nstatus == 1 
        ).distinct(rolesModel.Role.vcode)
        .all()
    )
    role_codes = [role.vcode for role in user_access_list]
    return role_codes