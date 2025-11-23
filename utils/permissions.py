"""
Shared permission utilities for role-based access control.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import Set

from ..services.schemas import usersSchema
from ..services.controller import userAccessController


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
