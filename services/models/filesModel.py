from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, CheckConstraint, UniqueConstraint
from sqlalchemy.sql import func 
from ..database import Base


class Files(Base):
    __tablename__ = "tblm_files"

    nid = Column(Integer, primary_key=True, autoincrement=True)

    vcode = Column(String(100), unique=True, index=True)
    vname = Column(String(255), nullable=False)
    vtype = Column(Text, nullable=False)
    vpath = Column(Text, nullable=False)
    vextension = Column(String(100), nullable=False)
    nsize = Column(Float, nullable=False)
    vcategory = Column(String(100), nullable=False)
    nis_public = Column(Integer, nullable=False, default=1)
    
    nstatus = Column(Integer, nullable=False, default=1)
    
    vcreated_by = Column(String(255), nullable=False)
    vmodified_by = Column(String(255), nullable=True)

    dcreated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    dmodified_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    dsort_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint('nis_public IN (0, 1)', name='chk_files_nis_public_values'),
        CheckConstraint('nstatus IN (0, 1)', name='chk_files_nstatus_values'),
        UniqueConstraint("vcode", "vname", name="uq_files_vcode_vname"),
    )