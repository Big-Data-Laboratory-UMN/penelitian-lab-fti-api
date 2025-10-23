from datetime import datetime
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Text, Boolean, Float, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func 
from ..database import Base


class Facility(Base):
    __tablename__ = "tblm_facility"

    nid = Column(Integer, primary_key=True, autoincrement=True)

    vcode = Column(String(100), unique=True, index=True)
    vname = Column(String(255), nullable=False)
    vdesc = Column(Text, nullable=False)
    
    nstatus = Column(Integer, nullable=False, default=1)
    
    nid_file = Column(Integer, ForeignKey("tblm_files.nid"), nullable=False)
    related_file_relationship = relationship("Files", backref="facilities", lazy="joined")
    
    vcreated_by = Column(String(255), nullable=False)
    vmodified_by = Column(String(255), nullable=True)

    dcreated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    dmodified_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    dsort_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint('nstatus IN (0, 1)', name='chk_facilities_nstatus_values'),
        UniqueConstraint("vcode", "vname", name="uq_facilities_vcode_vname"),
    )