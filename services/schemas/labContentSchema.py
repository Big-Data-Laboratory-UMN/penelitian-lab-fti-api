from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class LabContent(BaseModel):
    nid: int
    vcode: str
    vtitle: str
    vslug_url: str
    vsummary: str
    vcontent: str
    nstatus: int
    dcreated_at: Optional[datetime] = None
    vcreated_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None