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

class DepartmentLab(Base):
    __tablename__ = "tblr_department_lab"

    nid = Column(Integer, primary_key=True, autoincrement=True)

    vcode = Column(String(100), unique=True, index=True, nullable=False)

    nid_lab = Column(Integer, ForeignKey("tblm_lab.nid"), nullable=False)
    nid_department = Column(Integer, ForeignKey("tblm_department.nid"), nullable=False) 

    nstatus = Column(Integer, nullable=False, default=1)

    dcreated_at = Column(DateTime, default=now_wib)
    vcreated_by = Column(String(100), nullable=True)
    dmodified_at = Column(DateTime, onupdate=now_wib)
    vmodified_by = Column(String(100), nullable=True)
    
    dsort_at = Column(DateTime, default=now_wib, onupdate=now_wib)

    __table_args__ = (
        CheckConstraint('nstatus IN (0, 1)', name='chk_department_lab_nstatus_values'),
        UniqueConstraint("nid_lab", "nid_department", name="u_department_lab_combination"),
    )