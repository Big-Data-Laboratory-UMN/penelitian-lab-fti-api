from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class UserAccessCreate(BaseModel):
    vcode: str
    nid_user: int
    nid_role: int
    nid_department: int
    nid_lab: int
    vcreated_by: str = "system"

class UserAccessUpdate(BaseModel):
    vcode: str
    nid_user: int
    nid_role: int
    nid_department: int
    nid_lab: int
    nstatus: int
    vmodified_by: str = "system"

class UserAccess(BaseModel):
    nid: int
    vcode: str
    nid_user: int
    nid_role: int
    nid_department: int
    nid_lab: int
    nstatus: int
    dcreated_at: Optional[datetime] = None
    vcreated_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None

    class Config:
        from_attributes = True 

class UserAccessResponse(BaseModel):
    data: List[UserAccess]
    total: int

class UserAccessDropdown(BaseModel):
    nid: int
    vcode: str 

    class Config:
        from_attributes = True

class UserAccessDropdownResponse(BaseModel):
    data: List[UserAccessDropdown]