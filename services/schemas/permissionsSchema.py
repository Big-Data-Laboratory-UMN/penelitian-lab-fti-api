from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class PermissionCreate(BaseModel):
    vcode: str
    vname: str
    vdesc: str
    vcreated_by: str = "system" 

class PermissionUpdate(BaseModel):
    vcode: str
    vname: str
    vdesc: str
    nstatus: int
    vmodified_by: str = "system"

class Permission(BaseModel):
    nid: int
    vcode: str
    vname: str
    vdesc: str
    nstatus: int

    class Config:
        from_attributes = True

class PermissionResponse(BaseModel):
    data: List[Permission]
    total: int

class PermissionDropdown(BaseModel):
    nid: int
    vname: str

    class Config:
        from_attributes = True

class PermissionDropdownResponse(BaseModel):
    data: List[PermissionDropdown]