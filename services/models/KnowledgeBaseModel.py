from sqlalchemy import Column, Integer, Text, String, DateTime, CheckConstraint
from services.database import Base
from datetime import datetime
import pytz

def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

class knowledge_base(Base):
    __tablename__ = "tblm_knowledge_base"

    nid = Column(Integer, primary_key=True, autoincrement=True)
    vcategory=Column(String(255), nullable=True)
    vcontext=Column(Text, nullable=True)
    vanswer=Column(Text, nullable=True)
    nstatus=Column(Integer, nullable=False, default=1)

    dcreated_at = Column(DateTime, default=now_wib)
    vcreated_by = Column(String(100), nullable=True)
    dmodified_at = Column(DateTime, onupdate=now_wib)
    vmodified_by = Column(String(100), nullable=True)
    
    dsort_at = Column(DateTime, default=now_wib, onupdate=now_wib)

    __table_args__ = (
        CheckConstraint('nstatus IN (0, 1)', name='chk_knowledge_base_nstatus_values'),
    )