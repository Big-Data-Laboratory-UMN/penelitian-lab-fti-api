from datetime import datetime
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Text, Boolean, Float, CheckConstraint, UniqueConstraint
from sqlalchemy.sql import func 
from ..database import Base
import pytz


def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

class LabContentFiles(Base):
    __tablename__ = "tblr_lab_content_files"

    nid = Column(Integer, primary_key=True, autoincrement=True)

    vcode = Column(String(100), unique=True, index=True)
    nid_lab_content = Column(Integer,ForeignKey("tblr_lab_content.nid"), nullable=False)
    nid_file = Column(Integer,ForeignKey("tblm_files.nid"), nullable=False)

    vcreated_by = Column(String(100), nullable=True)
    dcreated_at = Column(DateTime, default=now_wib)
    vmodified_by = Column(String(100), nullable=True)
    dmodified_at = Column(DateTime, onupdate=now_wib)
    nstatus = Column(Integer, nullable=False, default=1)