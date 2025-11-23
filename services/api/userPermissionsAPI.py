from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from ..schemas import usersSchema
from ..controller import usersController
from ..database import SessionLocal
from utils import permissions

router = APIRouter(
    prefix="/user-permissions",
    tags=["User Permissions"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/accessible-labs", response_model=dict)
def get_accessible_labs(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Get list of lab IDs that the current user can access.
    Returns None for SA (all labs), empty list for VSTR, specific list for ADM/PIC.
    """
    accessible_labs = permissions.get_accessible_labs_for_user(db, current_user.nid)
    role_details = permissions.get_user_role_details(db, current_user.nid)
    
    return {
        "accessible_lab_ids": accessible_labs,
        "is_all_labs": accessible_labs is None,
        "highest_role": role_details['highest_role'],
        "can_edit_landing_page": permissions.can_edit_landing_page(db, current_user.nid)
    }

@router.get("/can-edit-lab-content/{lab_id}", response_model=dict)
def check_can_edit_lab_content(
    lab_id: int,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Check if current user can edit lab content for a specific lab."""
    can_edit = permissions.can_edit_lab_content(db, current_user.nid, lab_id)
    return {"can_edit": can_edit, "lab_id": lab_id}

@router.get("/can-edit-lab-gallery/{lab_id}", response_model=dict)
def check_can_edit_lab_gallery(
    lab_id: int,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Check if current user can edit lab gallery for a specific lab."""
    can_edit = permissions.can_edit_lab_gallery(db, current_user.nid, lab_id)
    return {"can_edit": can_edit, "lab_id": lab_id}
