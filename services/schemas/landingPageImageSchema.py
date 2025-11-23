from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class LandingPageImageCreate(BaseModel):
    vcode: str
    nid_file: int
    nid_landing_page_section: int
    vlandingpage_image_to_landingpage_vcode: str
    vcreated_by: str = "system"

class LandingPageImageUpdate(BaseModel):
    nid_file: int
    nstatus: int
    vmodified_by: str = "system"

class LandingPageImage(BaseModel):
    nid: int
    vcode: str
    nid_file: int
    nid_landing_page_section: int
    vlandingpage_image_to_landingpage_vcode: str
    vcreated_by: Optional[str] = None
    dcreated_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    nstatus: int

class LandingPageImageResponse(BaseModel):
    value: LandingPageImage
    found: bool