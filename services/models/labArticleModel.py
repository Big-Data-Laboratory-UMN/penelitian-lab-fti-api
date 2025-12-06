from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime
import pytz

def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))


class LabArticle(Base):
    """Article/News content for each Lab"""
    __tablename__ = "tblt_lab_article"
    
    nid = Column(Integer, primary_key=True, index=True, autoincrement=True)
    vcode = Column(String(100), unique=True, index=True)
    
    nid_lab = Column(Integer, ForeignKey('tblm_lab.nid'), nullable=False)
    nid_user = Column(Integer, ForeignKey('tbls_users.nid'), nullable=False)
    
    vtitle = Column(String(255), nullable=False)
    vexcerpt = Column(Text, nullable=True)  # Max 500 chars validated in schema
    vcontent = Column(Text, nullable=False)  # LONGTEXT, max 100k chars validated in schema
    nid_file = Column(Integer, ForeignKey("tblm_files.nid"), nullable=True)
    related_file = relationship("Files", backref="articles", lazy="joined")
    
    nis_featured = Column(Integer, default=0, comment="0:No, 1:Yes")
    nstatus = Column(Integer, default=1, comment="0:Inactive, 1:Published, 2:Scheduled")
    
    dpublished_at = Column(DateTime, nullable=True)
    
    dcreated_at = Column(DateTime, default=now_wib)
    vcreated_by = Column(String(100), nullable=True)
    dmodified_at = Column(DateTime, onupdate=now_wib)
    vmodified_by = Column(String(100), nullable=True)
    
    dsort_at = Column(DateTime, default=now_wib, onupdate=now_wib)
    
    # Relationships
    lab = relationship("Lab", backref="articles")
    author = relationship("User", backref="articles")
    tags = relationship("ArticleTag", back_populates="article", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint(
            "nis_featured IN (0, 1)",
            name="article_nis_featured_check"
        ),
        CheckConstraint(
            "nstatus IN (0, 1, 2)",
            name="article_nstatus_check"
        ),
    )


class ArticleTag(Base):
    """Tags for articles (max 5 per article enforced in schema)"""
    __tablename__ = "tblr_article_tag"
    
    nid = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nid_article = Column(Integer, ForeignKey('tblt_lab_article.nid', ondelete='CASCADE'), nullable=False)
    vtag = Column(String(100), nullable=False)
    
    # Relationship
    article = relationship("LabArticle", back_populates="tags")
