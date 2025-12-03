from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class LabCreate(BaseModel):
    vcode: str
    vname: str
    vdesc: str
    nid_building: int
    vroom_number: str
    ncapacity: int
    hero_image_vcode: Optional[str] = None
    gallery_image_vcodes: Optional[List[str]] = None
    vcreated_by: str = "system" 

class LabUpdate(BaseModel):
    vcode: str
    vname: str
    vdesc: str
    nid_building: int
    vroom_number: str
    ncapacity: int
    hero_image_vcode: Optional[str] = None
    gallery_image_vcodes: Optional[List[str]] = None
    nstatus: int
    vmodified_by: str = "system"

class Lab(BaseModel):
    nid: int
    vcode: str
    vname: str
    vdesc: str
    nid_building: int
    vroom_number: str
    ncapacity: int
    nstatus: int
    dcreated_at: Optional[datetime] = None
    vcreated_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None

    class Config:
        from_attributes = True

class LabResponse(BaseModel):
    data: List[Lab]
    total: int

class LabDropdown(BaseModel):
    nid: int
    vname: str

    class Config:
        from_attributes = True

class LabDropdownResponse(BaseModel):
    data: List[LabDropdown]