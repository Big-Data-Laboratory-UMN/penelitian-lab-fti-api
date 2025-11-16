from datetime import datetime
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Text, Boolean, Float, CheckConstraint, UniqueConstraint
from sqlalchemy.sql import func 
from ..database import Base
import pytz


def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

class LandingPageImages(Base):
    __tablename__ = "tbls_landing_page_image"

    nid = Column(Integer, primary_key=True, autoincrement=True)

    vcode = Column(String(100), unique=True, index=True)
    nid_file = Column(Integer,ForeignKey("tblm_files.nid"), nullable=False)
    nid_landing_page_section = Column(Integer,ForeignKey("tbls_landing_page.nid"), nullable=False)
    vlandingpage_image_to_landingpage_vcode = Column(String(100), nullable=False)
    vcreated_by = Column(String(100), nullable=True)
    dcreated_at = Column(DateTime, default=now_wib)
    vmodified_by = Column(String(100), nullable=True)
    dmodified_at = Column(DateTime, onupdate=now_wib)
    nstatus = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        CheckConstraint('nstatus IN (0, 1)', name='chk_landing_page_image_nstatus_values'),
        UniqueConstraint("vcode", "nid_landing_page_section", name="uq_landing_page_image_vcode_nid_section"),
    )