from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class LabContentFileCreate(BaseModel):
    vcode: str
    nid_lab_content: int
    vcode_lab_content: str
    nid_file: int
    vcreated_by: str = "system"

class LabContentFileUpdate(BaseModel):
    nstatus: int
    vmodified_by: str = "system"

class LabContentFile(BaseModel):
    nid: int
    vcode: str
    nid_lab_content: int
    vcode_lab_content: str
    nid_file: int
    vcreated_by: Optional[str] = None
    dcreated_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    nstatus: int

class LabContentFilesResponse(BaseModel):
    values: List[LabContentFile]
    total: Optional[int] = 0