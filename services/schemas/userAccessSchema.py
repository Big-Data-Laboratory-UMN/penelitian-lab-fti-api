# services/schemas/userAccessSchema.py

from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class UserAccessCreate(BaseModel):
    vcode: str
    nid_user: int
    nid_role: int
    
    # [MODIFIED] Dibuat optional
    nid_department: Optional[int] = None 
    
    # [NEW] Ditambah
    nid_lab: Optional[int] = None 
    
    vcreated_by: str = "system"

class UserAccessUpdate(BaseModel):
    vcode: str
    nid_user: int
    nid_role: int
    
    # [MODIFIED] Dibuat optional
    nid_department: Optional[int] = None 
    
    # [NEW] Ditambah
    nid_lab: Optional[int] = None 
    
    nstatus: int
    vmodified_by: str = "system"

class UserAccess(BaseModel):
    nid: int
    vcode: str
    nid_user: int
    nid_role: int
    
    # [MODIFIED] Dibuat optional
    nid_department: Optional[int] = None 
    
    # [NEW] Ditambah
    nid_lab: Optional[int] = None 
    
    nstatus: int
    dcreated_at: Optional[datetime] = None
    vcreated_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None

    class Config:
        from_attributes = True 

class UserAccessResponse(BaseModel):
    data: List[UserAccess]
    total: int

class UserAccessDropdown(BaseModel):
    nid: int
    vcode: str 

    class Config:
        from_attributes = True

class UserAccessDropdownResponse(BaseModel):
    data: List[UserAccessDropdown]