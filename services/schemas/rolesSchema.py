from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class RoleCreate(BaseModel):
    vcode: str
    vname: str
    vdesc: str
    vcreated_by: str = "system" 

class RoleUpdate(BaseModel):
    vcode: str 
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
    dcreated_at: Optional[datetime] = None
    vcreated_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None

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