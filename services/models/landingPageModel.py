# services/models/landingPageModel.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime
import pytz

def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))


class LandingPageContent(Base):
    """Single row table for landing page about section content"""
    __tablename__ = "tblm_landing_page_content"
    
    nid = Column(Integer, primary_key=True, index=True, autoincrement=True)
    vcode = Column(String(100), unique=True, index=True)
    
    # About Section
    vabout_header = Column(String(255), nullable=True, default="Heading text")
    vabout_subtext = Column(Text, nullable=True)
    
    # Timestamps
    dcreated_at = Column(DateTime, default=now_wib)
    vcreated_by = Column(String(100), nullable=True)
    dmodified_at = Column(DateTime, onupdate=now_wib)
    vmodified_by = Column(String(100), nullable=True)
    
    # Relationships
    slides = relationship("LandingPageSlide", back_populates="landing_page", cascade="all, delete-orphan")


class LandingPageSlide(Base):
    """Carousel slides for landing page (fixed 3 slides)"""
    __tablename__ = "tblm_landing_page_slide"
    
    nid = Column(Integer, primary_key=True, index=True, autoincrement=True)
    vcode = Column(String(100), unique=True, index=True)
    
    nid_landing_page = Column(Integer, ForeignKey('tblm_landing_page_content.nid'), nullable=False)
    
    norder = Column(Integer, nullable=False, comment="Slide order: 1, 2, or 3")
    vheader = Column(String(255), nullable=True, default="Slide Header")
    vsubtext = Column(Text, nullable=True)
    
    # Image file reference
    nid_file = Column(Integer, ForeignKey("tblm_files.nid"), nullable=True)
    related_file = relationship("Files", backref="landing_slides", lazy="joined")
    
    # Status: 0=Inactive, 1=Active
    nstatus = Column(Integer, default=1, comment="0:Inactive, 1:Active")
    
    # Timestamps
    dcreated_at = Column(DateTime, default=now_wib)
    vcreated_by = Column(String(100), nullable=True)
    dmodified_at = Column(DateTime, onupdate=now_wib)
    vmodified_by = Column(String(100), nullable=True)
    
    # Relationships
    landing_page = relationship("LandingPageContent", back_populates="slides")
    
    __table_args__ = (
        CheckConstraint(
            "norder IN (1, 2, 3)",
            name="slide_norder_check"
        ),
        CheckConstraint(
            "nstatus IN (0, 1)",
            name="slide_nstatus_check"
        ),
    )
