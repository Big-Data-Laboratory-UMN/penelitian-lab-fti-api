from sqlalchemy import (
    Column, 
    Integer, 
    String, 
    DateTime, 
    ForeignKey, 
    CheckConstraint, 
    UniqueConstraint
)
from datetime import datetime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base
import pytz


def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

class LabFacility(Base):
    __tablename__ = "tblr_lab_facility"

    nid = Column(Integer, primary_key=True, autoincrement=True)

    vcode = Column(String(100), unique=True, index=True, nullable=False)

    vcode_lab = Column(String(100), nullable=False)
    vcode_facility = Column(String(100), nullable=False)
    nid_lab = Column(Integer, ForeignKey("tblm_lab.nid"), nullable=False)
    nid_facility = Column(Integer, ForeignKey("tblm_facility.nid"), nullable=False) 

    nstatus = Column(Integer, nullable=False, default=1)

    dcreated_at = Column(DateTime, default=now_wib)
    vcreated_by = Column(String(100), nullable=True)
    dmodified_at = Column(DateTime, onupdate=now_wib)
    vmodified_by = Column(String(100), nullable=True)
    
    dsort_at = Column(DateTime, default=now_wib, onupdate=now_wib) 
    
    bookings = relationship("Booking", back_populates="lab_facility")
    lab = relationship("Lab", back_populates="lab_facilities")
    facility = relationship("Facility", back_populates="lab_facilities")

    __table_args__ = (
        CheckConstraint('nstatus IN (0, 1)', name='chk_facility_lab_nstatus_values'),
        UniqueConstraint("nid_lab", "nid_facility", name="u_facility_lab_combination"),
    )