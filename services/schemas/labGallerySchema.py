from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from .labSchema import LabDropdown

class LabGalleryCreate(BaseModel):
    vcode: str
    nid_lab: int
    nid_file: int
    vcreated_by: str = "system"

class LabGalleryUpdate(BaseModel):
    vcode: str
    nid_lab: int
    nid_file: int
    nstatus: int
    vmodified_by: str = "system"

class LabGallery(BaseModel):
    nid: int
    vcode: str
    nid_lab: int
    nid_file: int
    nstatus: int
    dcreated_at: Optional[datetime] = None
    vcreated_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None
    lab: Optional[LabDropdown] = None

    class Config:
        from_attributes = True

class LabGalleryResponse(BaseModel):
    data: List[LabGallery]
    total: int
