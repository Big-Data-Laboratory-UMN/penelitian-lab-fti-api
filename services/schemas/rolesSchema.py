from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class RoleCreate(BaseModel):
    vcode: str
    vname: str
    vdesc: str
    vcreated_by: str = "system" 

class RoleUpdate(BaseModel):
    vname: str
    vdesc: str
    nstatus: int
    vmodified_by: str = "system"

class Role(BaseModel):
    nid: int
    vcode: str
    vname: str
    vdesc: str
    nstatus: int

    class Config:
        from_attributes = True

class RoleResponse(BaseModel):
    data: List[Role]
    total: int

class RoleDropdown(BaseModel):
    nid: int
    vname: str

    class Config:
        from_attributes = True

class RoleDropdownResponse(BaseModel):
    data: List[RoleDropdown]