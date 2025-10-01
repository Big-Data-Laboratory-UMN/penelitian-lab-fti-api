from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, CheckConstraint
from sqlalchemy.sql import func 
from database import Base


class Role(Base):
    __tablename__ = "tblm_roles"

    nid = Column(Integer, primary_key=True, autoincrement=True)

    vcode = Column(String(100), unique=True, index=True)
    vname = Column(String(255), nullable=False)
    vdesc = Column(Text, nullable=False)
    vcreated_by = Column(String(255), nullable=False)
    vmodified_by = Column(String(255), nullable=True)

    dcreated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    dmodified_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    nstatus = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        CheckConstraint('nstatus IN (0, 1)', name='chk_nstatus_values'),
    )