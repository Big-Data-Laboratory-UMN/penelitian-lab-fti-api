from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from .labSchema import Lab as LabSchema
from .facilitySchema import Facility as FacilitySchema

class FacilityLabCreate(BaseModel):
    vcode: str
    nid_lab: int
    nid_facility: int
    vcreated_by: str = "system"
    vcode_lab: Optional[str] = None
    vcode_facility: Optional[str] = None

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
    vcode_lab: str
    nid_facility: int
    vcode_facility: str
    nstatus: int
    dcreated_at: Optional[datetime] = None
    vcreated_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None
    
    lab: Optional[LabSchema] = None
    facility: Optional[FacilitySchema] = None

    class Config:
        from_attributes = True 

class FacilityLabResponse(BaseModel):
    data: List[FacilityLab]
    total: int

class FacilityLabDropdown(BaseModel):
    nid: int
    vcode: str 
    vname: Optional[str] = None # Add vname for facility name

    class Config:
        from_attributes = True

class FacilityLabDropdownResponse(BaseModel):
    data: List[FacilityLabDropdown]
    total: Optional[int] = None # Add total count

class FacilityLabAnonymous(BaseModel):
    nid: int
    vcode: str
    vcode_facility: str
    vname: str
    vdesc: Optional[str] = None
    nid_file: Optional[int] = None

class FacilityLabAnonymousResponse(BaseModel):
    data: List[FacilityLabAnonymous]
    total: int