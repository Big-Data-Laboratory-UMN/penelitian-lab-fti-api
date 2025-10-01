from pydantic import BaseModel
from datetime import datetime

class Role(BaseModel):
    nid: int
    vcode: str
    vname: str
    vdesc: str
    nstatus: int

    class Config:
        orm_mode = True