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
import pytz


def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

class RolePermission(Base):
    """
    Tabel relasi (join table) untuk menentukan permission apa saja 
    yang dimiliki oleh sebuah role (Many-to-Many).
    """
    __tablename__ = "tblr_role_permissions"

    nid = Column(Integer, primary_key=True, autoincrement=True)

    vcode = Column(String(100), unique=True, index=True, nullable=False)

    nid_role = Column(Integer, ForeignKey("tblm_roles.nid"), nullable=False)
    nid_permission = Column(Integer, ForeignKey("tblm_permissions.nid"), nullable=False) 

    nstatus = Column(Integer, nullable=False, default=1)

    dcreated_at = Column(DateTime, default=now_wib)
    vcreated_by = Column(String(100), nullable=True)
    dmodified_at = Column(DateTime, onupdate=now_wib)
    vmodified_by = Column(String(100), nullable=True)
    
    dsort_at = Column(DateTime, default=now_wib, onupdate=now_wib) 

    __table_args__ = (
        CheckConstraint('nstatus IN (0, 1)', name='chk_role_permissions_nstatus_values'),
        UniqueConstraint("nid_role", "nid_permission", name="uq_role_permission_combination"),
    )