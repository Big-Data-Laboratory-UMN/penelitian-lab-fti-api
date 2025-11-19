from sqlalchemy import (
    Column, 
    Integer, 
    String, 
    DateTime, 
    ForeignKey, 
    CheckConstraint, 
    UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy.sql import func
from ..database import Base
import pytz


def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

class UserAccess(Base):
    __tablename__ = "tblr_user_access"

    nid = Column(Integer, primary_key=True, autoincrement=True)

    vcode = Column(String(100), unique=True, index=True, nullable=False)

    nid_user = Column(Integer, ForeignKey("tbls_users.nid"), nullable=False) 
    nid_role = Column(Integer, ForeignKey("tblm_roles.nid"), nullable=False)
    
    nid_department = Column(Integer, ForeignKey("tblm_department.nid"), nullable=True) 
    
    nid_lab = Column(Integer, ForeignKey("tblm_lab.nid"), nullable=True)

    nstatus = Column(Integer, nullable=False, default=1)

    dcreated_at = Column(DateTime, default=now_wib)
    vcreated_by = Column(String(100), nullable=True)
    dmodified_at = Column(DateTime, onupdate=now_wib)
    vmodified_by = Column(String(100), nullable=True)
    
    dsort_at = Column(DateTime, default=now_wib, onupdate=now_wib) 

    user = relationship("User", back_populates="user_access_rel")
    role = relationship("Role", back_populates="user_access_rel")

    __table_args__ = (
        CheckConstraint('nstatus IN (0, 1)', name='chk_user_access_nstatus_values'),
        
        UniqueConstraint("nid_user", "nid_role", "nid_department", "nid_lab", name="uq_user_access_combination"),
    )