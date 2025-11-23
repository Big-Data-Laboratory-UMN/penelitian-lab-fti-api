from datetime import datetime
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Text, Boolean, Float, CheckConstraint, UniqueConstraint
from sqlalchemy.sql import func 
from ..database import Base
import pytz


def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

class LandingPages(Base):
    __tablename__ = "tbls_landing_page"

    nid = Column(Integer, primary_key=True, autoincrement=True)

    vcode = Column(String(100), unique=True, index=True)
    vsection_name = Column(String(255), nullable=False)
    vdesc = Column(Text, nullable=False)
    vtitle = Column(String(255), nullable=False)
    vcreated_by = Column(String(100), nullable=True)
    dcreated_at = Column(DateTime, default=now_wib)
    vmodified_by = Column(String(100), nullable=True)
    dmodified_at = Column(DateTime, onupdate=now_wib)
    nstatus = Column(Integer, nullable=False, default=1)
    nid_image = Column(Integer,ForeignKey("tblm_files.nid"), nullable=True)

    __table_args__ = (
        CheckConstraint('nstatus IN (0, 1)', name='chk_landing_page_nstatus_values'),
        UniqueConstraint("vcode", "vsection_name", name="uq_landing_page_vcode_vsection_name"),
    )