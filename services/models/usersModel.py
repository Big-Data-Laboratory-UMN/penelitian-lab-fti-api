from datetime import datetime
from sqlalchemy import (
    Column, 
    Integer, 
    String, 
    DateTime, 
    Text,
    CheckConstraint 
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base
import pytz

def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

# Status User: 0=Inactive, 1=Active, 2=Pending, 3=Expired

class User(Base):
    __tablename__ = "tbls_users"

    nid = Column(Integer, primary_key=True, autoincrement=True)
    vcode = Column(String(100), unique=True, index=True)
    vname = Column(String(255), nullable=False)
    vphone = Column(String(20), nullable=True)
    vemail = Column(String(255), unique=True, index=True, nullable=False)
    vaddress = Column(Text, nullable=True)
    
    vpassword = Column(String(255), nullable=True)

    nstatus = Column(Integer, nullable=False, default=1, comment="Status User: 0=Inactive, 1=Active, 2=Pending, 3=Expired")
    
    dcreated_at = Column(DateTime, default=now_wib)
    vcreated_by = Column(String(100), nullable=True)
    dmodified_at = Column(DateTime, onupdate=now_wib)
    vmodified_by = Column(String(100), nullable=True)
    
    dsort_at = Column(DateTime, default=now_wib, onupdate=now_wib) 
    
    bookings = relationship("Booking", back_populates="user")
    
    user_access_rel = relationship("UserAccess", back_populates="user")
    
    __table_args__ = (
        CheckConstraint(
            nstatus.in_([0, 1, 2, 3]), 
            name='chk_users_nstatus_values'
        ),
    )