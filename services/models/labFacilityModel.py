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
from ..database import Base

class LabFacility(Base):
    __tablename__ = "tblr_lab_facility"

    nid = Column(Integer, primary_key=True, autoincrement=True)

    vcode = Column(String(100), unique=True, index=True, nullable=False)

    nid_lab = Column(Integer, ForeignKey("tblm_lab.nid"), nullable=False)
    nid_facility = Column(Integer, ForeignKey("tblm_facility.nid"), nullable=False) 

    nstatus = Column(Integer, nullable=False, default=1)

    vcreated_by = Column(String(255), nullable=False)
    vmodified_by = Column(String(255), nullable=True)
    dcreated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    dmodified_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    dsort_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint('nstatus IN (0, 1)', name='chk_facility_lab_nstatus_values'),
        UniqueConstraint("nid_lab", "nid_facility", name="u_facility_lab_combination"),
    )