from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship

from ..database import Base 
from .usersModel import User # Import User model
import pytz
from datetime import datetime

# Ambil dari model lu yang lain
def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

class ActivityLog(Base):
    __tablename__ = "tblh_activity_logs"

    nid = Column(Integer, primary_key=True, autoincrement=True)
    
    # Siapa yg ngelakuin (WAJIB ADA)
    nid_user = Column(Integer, ForeignKey("tbls_users.nid"), nullable=False, index=True) 
    
    # Aksi: 'CREATE', 'UPDATE', 'DELETE'
    vaction = Column(String(50), nullable=False, index=True)
    
    # Model apa yg diubah: 'Role', 'Booking', 'Lab', 'UserAccess'
    vtarget_model = Column(String(100), nullable=False, index=True)
    
    # ID dari data yg diubah (bisa nid atau vcode)
    vtarget_identifier = Column(String(255), nullable=False, index=True) 
    
    # Data lama (buat CREATE ini null)
    # Pake JSONB kalo pake Postgres, ganti ke JSON kalo pake MySQL/SQLite
    jbefore = Column(JSON, nullable=True) 
    
    # Data baru (buat DELETE ini null)
    jafter = Column(JSON, nullable=True)
    
    dtimestamp = Column(DateTime, default=now_wib, index=True)
    vip_address = Column(String(100), nullable=True)
    vuser_agent = Column(Text, nullable=True)
    
    # Relasi wajib
    user = relationship("User")