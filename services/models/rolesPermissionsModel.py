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

    vcreated_by = Column(String(255), nullable=False)
    vmodified_by = Column(String(255), nullable=True)
    dcreated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    dmodified_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    dsort_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint('nstatus IN (0, 1)', name='chk_role_permissions_nstatus_values'),
        UniqueConstraint("nid_role", "nid_permission", name="uq_role_permission_combination"),
    )