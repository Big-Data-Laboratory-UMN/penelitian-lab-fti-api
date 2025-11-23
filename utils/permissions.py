"""
Shared permission utilities for role-based access control.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import Set, Optional, List, Dict

from services.schemas import usersSchema
from services.controller import userAccessController
from services.models import userAccessModel, departmentLabModel


def require_roles(
    db: Session,
    current_user: usersSchema.User,
    allowed_roles: Set[str],
    resource_name: str = "resource"
) -> None:
    """
    Check if the current user has any of the allowed roles.
    
    Args:
        db: Database session
        current_user: The authenticated user
        allowed_roles: Set of allowed role codes (e.g., {"SA", "ADM", "PIC"})
        resource_name: Name of the resource for error message
        
    Raises:
        HTTPException: 403 if user doesn't have required role
    """
    user_roles = set(userAccessController.get_user_roles_by_user_id(
        db=db, 
        user_id=current_user.nid
    ))
    
    if not (user_roles & allowed_roles):
        allowed_list = "/".join(sorted(allowed_roles))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role tidak diizinkan untuk operasi {resource_name} (butuh {allowed_list})."
        )


def get_user_role_details(db: Session, user_id: int) -> Dict[str, any]:
    """
    Get detailed role information for a user including department and lab assignments.
    
    Returns:
        {
            'roles': ['SA', 'ADM'],
            'highest_role': 'SA',
            'departments': [1, 2],
            'labs': [3, 4]
        }
    """
    user_access_records = (
        db.query(userAccessModel.UserAccess)
        .join(userAccessModel.UserAccess.role)
        .filter(
            userAccessModel.UserAccess.nid_user == user_id,
            userAccessModel.UserAccess.nstatus == 1
        )
        .all()
    )
    
    roles = set()
    departments = set()
    labs = set()
    
    for record in user_access_records:
        if record.role and record.role.nstatus == 1:
            roles.add(record.role.vcode)
        if record.nid_department:
            departments.add(record.nid_department)
        if record.nid_lab:
            labs.add(record.nid_lab)
    
    # Determine highest role (SA > ADM > PIC > VSTR)
    role_hierarchy = {'SA': 1, 'ADM': 2, 'PIC': 3, 'VSTR': 4}
    highest_role = None
    if roles:
        highest_role = min(roles, key=lambda r: role_hierarchy.get(r, 99))
    
    return {
        'roles': list(roles),
        'highest_role': highest_role,
        'departments': list(departments),
        'labs': list(labs)
    }


def get_accessible_labs_for_user(db: Session, user_id: int) -> List[int]:
    """
    Get list of lab IDs that a user can access based on their role.
    
    - SA: all labs
    - ADM: labs in their departments
    - PIC: only their assigned labs
    - VSTR: no labs
    """
    role_details = get_user_role_details(db, user_id)
    highest_role = role_details['highest_role']
    
    if highest_role == 'SA':
        # SA has access to all labs
        return None  # None means "all labs"
    
    elif highest_role == 'ADM':
        # ADM has access to labs in their departments
        if not role_details['departments']:
            return []
        
        lab_ids = (
            db.query(departmentLabModel.DepartmentLab.nid_lab)
            .filter(
                departmentLabModel.DepartmentLab.nid_department.in_(role_details['departments']),
                departmentLabModel.DepartmentLab.nstatus == 1
            )
            .distinct()
            .all()
        )
        return [lab_id[0] for lab_id in lab_ids]
    
    elif highest_role == 'PIC':
        # PIC has access only to their assigned labs
        return role_details['labs']
    
    else:
        # VSTR or unknown role has no access
        return []


def check_lab_access(
    db: Session,
    current_user: usersSchema.User,
    lab_id: int,
    resource_name: str = "resource"
) -> None:
    """
    Check if user has access to a specific lab.
    
    Raises:
        HTTPException: 403 if user doesn't have access to the lab
    """
    accessible_labs = get_accessible_labs_for_user(db, current_user.nid)
    
    # None means all labs (SA)
    if accessible_labs is None:
        return
    
    if lab_id not in accessible_labs:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Anda tidak memiliki akses ke {resource_name} pada lab ini."
        )


def can_edit_lab_content(db: Session, user_id: int, lab_id: int) -> bool:
    """
    Check if user can edit lab content for a specific lab.
    SA, ADM (if lab in their dept), and PIC (if lab assigned) can edit.
    """
    role_details = get_user_role_details(db, user_id)
    highest_role = role_details['highest_role']
    
    if highest_role == 'SA':
        return True
    
    accessible_labs = get_accessible_labs_for_user(db, user_id)
    if accessible_labs is None:  # SA
        return True
    
    return lab_id in accessible_labs


def can_edit_lab_gallery(db: Session, user_id: int, lab_id: int) -> bool:
    """
    Check if user can edit lab gallery for a specific lab.
    Only SA and ADM (if lab in their dept) can edit. PIC cannot.
    """
    role_details = get_user_role_details(db, user_id)
    highest_role = role_details['highest_role']
    
    if highest_role == 'SA':
        return True
    
    if highest_role == 'ADM':
        accessible_labs = get_accessible_labs_for_user(db, user_id)
        if accessible_labs is None:  # SA
            return True
        return lab_id in accessible_labs
    
    return False  # PIC and VSTR cannot edit gallery


def can_edit_landing_page(db: Session, user_id: int) -> bool:
    """
    Check if user can edit landing page.
    Only SA can edit landing pages.
    """
    role_details = get_user_role_details(db, user_id)
    return role_details['highest_role'] == 'SA'
