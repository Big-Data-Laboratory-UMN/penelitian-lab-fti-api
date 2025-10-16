from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class DepartmentLabCreate(BaseModel):
    vcode: str
    nid_lab: int
    nid_department: int
    vcreated_by: str = "system"

class DepartmentLabUpdate(BaseModel):
    vcode: str
    nid_lab: int
    nid_department: int
    nstatus: int
    vmodified_by: str = "system"

class DepartmentLab(BaseModel):
    nid: int
    vcode: str
    nid_lab: int
    nid_department: int
    nstatus: int
    dcreated_at: Optional[datetime] = None
    vcreated_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None

    class Config:
        from_attributes = True 

class DepartmentLabResponse(BaseModel):
    data: List[DepartmentLab]
    total: int

class DepartmentLabDropdown(BaseModel):
    nid: int
    vcode: str 

    class Config:
        from_attributes = True

class DepartmentLabDropdownResponse(BaseModel):
    data: List[DepartmentLabDropdown]