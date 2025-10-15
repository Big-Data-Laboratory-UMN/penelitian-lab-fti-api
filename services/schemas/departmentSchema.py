from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class DepartmentCreate(BaseModel):
    vcode: str
    vname: str
    vdesc: str
    vcreated_by: str = "system" 

class DepartmentUpdate(BaseModel):
    vcode: str
    vname: str
    vdesc: str
    nstatus: int
    vmodified_by: str = "system"

class Department(BaseModel):
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

class DepartmentResponse(BaseModel):
    data: List[Department]
    total: int

class DepartmentDropdown(BaseModel):
    nid: int
    vname: str

    class Config:
        from_attributes = True

class DepartmentDropdownResponse(BaseModel):
    data: List[DepartmentDropdown]