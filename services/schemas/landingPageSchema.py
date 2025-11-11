from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

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