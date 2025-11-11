from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class LabContentFiles(BaseModel):
    nid: int
    vcode: str
    nid_lab_content: int
    nid_file: int
    vcreated_by: Optional[str] = None
    dcreated_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    nstatus: int

class LabContentFilesResponse(BaseModel):
    value: LabContentFiles | None
    found: bool