# services/schemas/bookingSchema.py

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from .bookingFilesSchema import BookingFileSchema
from .usersSchema import User as UserSchema
from .labFacilitySchema import FacilityLab as LabFacilitySchema

class BookingBase(BaseModel):
    nid_lab_facility: int
    dstart: datetime
    dend: datetime
    vactivity: str

class BookingCreate(BookingBase):
    pass

class BookingUpdate(BaseModel):
    nstatus: Optional[int] = None

class BookingSchema(BookingBase):
    nid: int
    vcode: str
    nid_user: int
    nstatus: int

    dreviewed_at: Optional[datetime] = None
    vreviewed_by: Optional[str] = None

    vcreated_by: str
    dcreated_at: datetime
    vmodified_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None

    user: Optional[UserSchema] = None 
    lab_facility: Optional[LabFacilitySchema] = None 
    booking_files: List[BookingFileSchema] = [] 

    class Config:
        from_attributes = True

class BookingResponse(BaseModel):
    data: List[BookingSchema]
    total: int