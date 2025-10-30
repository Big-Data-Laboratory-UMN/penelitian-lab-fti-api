from sqlalchemy import (
    Column, 
    Integer, 
    String, 
    DateTime, 
    ForeignKey, 
    CheckConstraint, 
    UniqueConstraint
)
from datetime import datetime
from sqlalchemy.sql import func
from ..database import Base

class UserAccess(Base):
    __tablename__ = "tblr_user_access"

    nid = Column(Integer, primary_key=True, autoincrement=True)

    vcode = Column(String(100), unique=True, index=True, nullable=False)

    nid_user = Column(Integer, ForeignKey("tbls_users.nid"), nullable=False) 
    nid_role = Column(Integer, ForeignKey("tblm_roles.nid"), nullable=False)
    
    nid_department = Column(Integer, ForeignKey("tblm_department.nid"), nullable=True) 
    
    nid_lab = Column(Integer, ForeignKey("tblm_lab.nid"), nullable=True)

    nstatus = Column(Integer, nullable=False, default=1)

    vcreated_by = Column(String(255), nullable=False)
    vmodified_by = Column(String(255), nullable=True)
    dcreated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    dmodified_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    dsort_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint('nstatus IN (0, 1)', name='chk_user_access_nstatus_values'),
        
        UniqueConstraint("nid_user", "nid_role", "nid_department", "nid_lab", name="uq_user_access_combination"),
    )