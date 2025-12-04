from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class KnowledgeBaseCreate(BaseModel):
    vcategory: str
    vcontext: str
    vanswer: str
    nstatus: int
    vcreated_by: Optional[str] = "system"

class KnowledgeBaseUpdate(BaseModel):
    vcategory: str
    vcontext: str
    vanswer: str
    nstatus: int
    vmodified_by: Optional[str] = "system"

class KnowledgeBase(BaseModel):
    nid: int
    vcategory: Optional[str]
    vcontext: Optional[str]
    vanswer: Optional[str]
    nstatus: int
    dcreated_at: Optional[datetime] = None
    vcreated_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None
    dsort_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class KnowledgeBaseResponse(BaseModel):
    data: List[KnowledgeBase]
    total: int
