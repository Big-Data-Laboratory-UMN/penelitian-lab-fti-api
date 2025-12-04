from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class BuildingCreate(BaseModel):
    vcode: str
    vname: str
    vdesc: str
    vcreated_by: str = "system" 

class BuildingUpdate(BaseModel):
    vcode: str 
    vname: str
    vdesc: str
    nstatus: int
    vmodified_by: str = "system"

class Building(BaseModel):
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

class BuildingResponse(BaseModel):
    data: List[Building]
    total: int

class BuildingDropdown(BaseModel):
    nid: int
    vname: str

    class Config:
        from_attributes = True

class BuildingDropdownResponse(BaseModel):
    data: List[BuildingDropdown]