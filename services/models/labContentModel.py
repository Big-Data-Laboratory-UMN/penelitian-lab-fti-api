from datetime import datetime
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Text, Boolean, Float, CheckConstraint, UniqueConstraint
from sqlalchemy.sql import func 
from ..database import Base
import pytz


def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

class LabContent(Base):
    __tablename__ = "tblr_lab_content"

    nid = Column(Integer, primary_key=True, autoincrement=True)

    vcode = Column(String(100), unique=True, index=True)
    nid_lab = Column(Integer,ForeignKey("tblm_lab.nid"), nullable=False)
    
    vtitle = Column(String(255), nullable=False)
    vslug_url = Column(String(255), nullable=False)
    vsummary = Column(Text, nullable=False)
    vcontent = Column(Text, nullable=False)
    nstatus = Column(Integer, nullable=False, default=1)
    vcreated_by = Column(String(100), nullable=True)
    dcreated_at = Column(DateTime, default=now_wib)
    vmodified_by = Column(String(100), nullable=True)
    dmodified_at = Column(DateTime, onupdate=now_wib)

    __table_args__ = (
        CheckConstraint('nstatus IN (0, 1)', name='chk_lab_content_nstatus_values'),
        UniqueConstraint("vcode", "vtitle", name="uq_lab_content_vcode_vtitle"),
    )