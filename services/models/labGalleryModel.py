from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship
from ..database import Base
import pytz

def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

class LabGallery(Base):
    __tablename__ = "tblr_lab_gallery"

    nid = Column(Integer, primary_key=True, autoincrement=True)
    vcode = Column(String(100), unique=True, index=True)
    
    nid_lab = Column(Integer, ForeignKey("tblm_lab.nid"), nullable=False)
    nid_file = Column(Integer, ForeignKey("tblm_files.nid"), nullable=False)
    
    nstatus = Column(Integer, nullable=False, default=1)
    
    dcreated_at = Column(DateTime, default=now_wib)
    vcreated_by = Column(String(100), nullable=True)
    dmodified_at = Column(DateTime, onupdate=now_wib)
    vmodified_by = Column(String(100), nullable=True)

    lab = relationship("Lab", backref="gallery_images")
    file = relationship("Files")

    __table_args__ = (
        CheckConstraint('nstatus IN (0, 1)', name='chk_lab_gallery_nstatus_values'),
        UniqueConstraint("nid_lab", "nid_file", name="uq_lab_gallery_lab_file"),
    )
