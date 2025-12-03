from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, CheckConstraint, UniqueConstraint, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func 
from ..database import Base
import pytz


def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

class Lab(Base):
    __tablename__ = "tblm_lab"

    nid = Column(Integer, primary_key=True, autoincrement=True)

    vcode = Column(String(100), unique=True, index=True)
    vname = Column(String(255), nullable=False)
    vdesc = Column(Text, nullable=False)
    
    ncapacity = Column(Integer, nullable=False)

    nid_building = Column(Integer, ForeignKey("tblm_building.nid"), nullable=False)
    vroom_number = Column(String(100), nullable=False)
    
    nstatus = Column(Integer, nullable=False, default=1)
    
    dcreated_at = Column(DateTime, default=now_wib)
    vcreated_by = Column(String(100), nullable=True)
    dmodified_at = Column(DateTime, onupdate=now_wib)
    vmodified_by = Column(String(100), nullable=True)
    
    dsort_at = Column(DateTime, default=now_wib, onupdate=now_wib) 
    
    lab_facilities = relationship("LabFacility", back_populates="lab")
    building = relationship("Building", back_populates="lab_rel")

    __table_args__ = (
        CheckConstraint('nstatus IN (0, 1)', name='chk_lab_nstatus_values'),
        UniqueConstraint("vcode", "vname", name="uq_lab_vcode_vname"),
    )