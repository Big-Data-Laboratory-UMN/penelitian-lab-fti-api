from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime


class LabContentCreate(BaseModel):
    vcode: str
    nid_lab: int
    vtitle: str
    vslug_url: str
    vsummary: str
    vcontent: str
    vcreated_by: str = "system"


class LabContentUpdate(BaseModel):
    vcode: str
    nid_lab: int
    vtitle: str
    vslug_url: str
    vsummary: str
    vcontent: str
    nstatus: int
    vmodified_by: str = "system"


class LabContent(BaseModel):
    nid: int
    vcode: str
    nid_lab: int
    vtitle: str
    vslug_url: str
    vsummary: str
    vcontent: str
    nstatus: int
    dcreated_at: Optional[datetime] = None
    vcreated_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None

class LabContentResponse(BaseModel):
    data: List[LabContent]
    total: int