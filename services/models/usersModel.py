from datetime import datetime
from sqlalchemy import (
    Column, 
    Integer, 
    String, 
    DateTime, 
    Text,
    CheckConstraint 
)
from sqlalchemy.sql import func
from ..database import Base

# Status User: 0=Inactive, 1=Active, 2=Pending, 3=Expired

class User(Base):
    __tablename__ = "tbls_users"

    nid = Column(Integer, primary_key=True, autoincrement=True)
    vcode = Column(String(100), unique=True, index=True)
    vname = Column(String(255), nullable=False)
    vphone = Column(String(20), nullable=True)
    vemail = Column(String(255), unique=True, index=True, nullable=False)
    vaddress = Column(Text, nullable=True)
    vinstitution = Column(String(255), nullable=True)
    
    vpassword = Column(String(255), nullable=True)

    nstatus = Column(Integer, nullable=False, default=1, comment="Status User: 0=Inactive, 1=Active, 2=Pending, 3=Expired")
    vcreated_by = Column(String(255), nullable=False)
    vmodified_by = Column(String(255), nullable=True)
    dcreated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    dmodified_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    dsort_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint(
            nstatus.in_([0, 1, 2, 3]), 
            name='chk_users_nstatus_values'
        ),
    )