from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class RolePermissionCreate(BaseModel):
    """
    Schema untuk membuat relasi role-permission baru.
    """
    vcode: str
    nid_role: int
    nid_permission: int
    vcreated_by: str = "system"

class RolePermissionUpdate(BaseModel):
    """
    Schema untuk mengupdate relasi role-permission.
    """
    vcode: str
    nid_role: int
    nid_permission: int
    nstatus: int
    vmodified_by: str = "system"

class RolePermission(BaseModel):
    """
    Schema dasar untuk data relasi role-permission.
    """
    nid: int
    vcode: str
    nid_role: int
    nid_permission: int
    nstatus: int
    dcreated_at: Optional[datetime] = None
    vcreated_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None

    class Config:
        from_attributes = True 

class RolePermissionResponse(BaseModel):
    """
    Schema untuk response list data dengan paginasi.
    """
    data: List[RolePermission]
    total: int

class RolePermissionDropdown(BaseModel):
    """
    Schema sederhana untuk kebutuhan dropdown.
    """
    nid: int
    vcode: str 

    class Config:
        from_attributes = True

class RolePermissionDropdownResponse(BaseModel):
    """
    Schema untuk response list data dropdown.
    """
    data: List[RolePermissionDropdown]