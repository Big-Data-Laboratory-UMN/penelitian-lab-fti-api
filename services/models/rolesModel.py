from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, CheckConstraint, UniqueConstraint
from sqlalchemy.sql import func 
from ..database import Base
import pytz


def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

class Role(Base):
    __tablename__ = "tblm_roles"

    nid = Column(Integer, primary_key=True, autoincrement=True)

    vcode = Column(String(100), unique=True, index=True)
    vname = Column(String(255), nullable=False)
    vdesc = Column(Text, nullable=False)
    
    nstatus = Column(Integer, nullable=False, default=1)
    
    dcreated_at = Column(DateTime, default=now_wib)
    vcreated_by = Column(String(100), nullable=True)
    dmodified_at = Column(DateTime, onupdate=now_wib)
    vmodified_by = Column(String(100), nullable=True)
    
    dsort_at = Column(DateTime, default=now_wib, onupdate=now_wib)

    __table_args__ = (
        CheckConstraint('nstatus IN (0, 1)', name='chk_roles_nstatus_values'),
        UniqueConstraint("vcode", "vname", name="uq_roles_vcode_vname"),
    )