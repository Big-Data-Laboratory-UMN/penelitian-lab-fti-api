from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class LandingPageCreate(BaseModel):
    vcode: str
    vsection_name: str
    vtitle: str
    vdesc: str
    nid_image: Optional[int] = None
    vcreated_by: str = "system"

class LandingPageUpdate(BaseModel):
    vcode: str
    vsection_name: str
    vtitle: str
    vdesc: str
    nid_image: Optional[int] = None
    nstatus: int
    vmodified_by: str = "system"

class LandingPage(BaseModel):
    nid: int
    vcode: str
    vsection_name: str
    vtitle: str
    vdesc: str
    vcreated_by: Optional[str] = None
    dcreated_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    nstatus: int
    nid_image: Optional[int] = None

class LandingPageResponse(BaseModel):
    data: List[LandingPage]
    total: int