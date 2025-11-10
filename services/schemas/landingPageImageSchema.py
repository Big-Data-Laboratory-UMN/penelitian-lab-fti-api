from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class LandingPageImage(BaseModel):
    nid: int
    vcode: str
    nid_file: int
    nid_landing_page_section: int
    vcreated_by: Optional[str] = None
    dcreated_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    nstatus: int