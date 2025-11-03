from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func, Text
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime
import pytz

def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

class Booking(Base):
    __tablename__ = "tblt_booking"
    
    nid = Column(Integer, primary_key=True, index=True, autoincrement=True)
    vcode = Column(String(100), unique=True, index=True)
    nid_lab_facility = Column(Integer, ForeignKey('tblr_lab_facility.nid'), nullable=False)
    nid_user = Column(Integer, ForeignKey('tbls_users.nid'), nullable=False) 
    
    dstart = Column(DateTime, nullable=False)
    dend = Column(DateTime, nullable=False)
    vactivity = Column(Text, nullable=True)
    
    nstatus = Column(Integer, default=2, comment="0:Rejected, 1:Approved, 2:Pending, 3:Canceled, 4:WaitingForDoc, 5:Done")
    
    dreviewed_at = Column(DateTime, nullable=True)
    vreviewed_by = Column(String(100), nullable=True)

    dcreated_at = Column(DateTime, default=now_wib)
    vcreated_by = Column(String(100), nullable=True)
    dmodified_at = Column(DateTime, onupdate=now_wib)
    vmodified_by = Column(String(100), nullable=True)
    
    dsort_at = Column(DateTime, default=now_wib, onupdate=now_wib) 
    
    # Relationships
    user = relationship("User", back_populates="bookings")
    lab_facility = relationship("LabFacility", back_populates="bookings")
    booking_files = relationship("BookingFile", back_populates="booking", 
                                 primaryjoin="and_(Booking.nid == BookingFile.nid_booking, BookingFile.nstatus == 1)")