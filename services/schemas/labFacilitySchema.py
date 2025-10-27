from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class FacilityLabCreate(BaseModel):
    vcode: str
    nid_lab: int
    nid_facility: int
    vcreated_by: str = "system"

class FacilityLabUpdate(BaseModel):
    vcode: str
    nid_lab: int
    nid_facility: int
    nstatus: int
    vmodified_by: str = "system"

class FacilityLab(BaseModel):
    nid: int
    vcode: str
    nid_lab: int
    nid_facility: int
    nstatus: int
    dcreated_at: Optional[datetime] = None
    vcreated_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None

    class Config:
        from_attributes = True 

class FacilityLabResponse(BaseModel):
    data: List[FacilityLab]
    total: int

class FacilityLabDropdown(BaseModel):
    nid: int
    vcode: str 

    class Config:
        from_attributes = True

class FacilityLabDropdownResponse(BaseModel):
    data: List[FacilityLabDropdown]