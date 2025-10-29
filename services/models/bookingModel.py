from sqlalchemy import CheckConstraint, Column, Integer, DateTime, ForeignKey, func, String, Text
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime 

class Booking(Base):
    __tablename__ = 'tblt_booking'

    nid = Column(Integer, primary_key=True, autoincrement=True) 
    vcode = Column(String(100), unique=True, index=True, nullable=False) 

    nid_lab_facility = Column(Integer, ForeignKey('tblr_lab_facility.nid'), nullable=False) 

    nid_user = Column(Integer, ForeignKey('tbls_users.nid'), nullable=False) 

    dstart = Column(DateTime, nullable=False) 
    dend = Column(DateTime, nullable=False) 

    vactivity = Column(Text, nullable=False) 

    nstatus = Column(Integer, nullable=False, default=2) 
    
    vcreated_by = Column(String(255), nullable=False) 
    vmodified_by = Column(String(255), nullable=True)

    dcreated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    dmodified_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    dsort_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) 

    user = relationship("User", back_populates="bookings") 
    lab_facility = relationship("LabFacility", back_populates="bookings") 

    booking_files = relationship("BookingFile", back_populates="booking") 

    __table_args__ = (
        CheckConstraint('dend > dstart', name='chk_booking_dates'), 
    )