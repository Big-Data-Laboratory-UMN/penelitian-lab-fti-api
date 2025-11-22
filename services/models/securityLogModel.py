from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base 
from .usersModel import User # Import User model
import pytz
from datetime import datetime

# Ambil dari model lu yang lain
def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

class SecurityLog(Base):
    __tablename__ = "tblh_security_logs"

    nid = Column(Integer, primary_key=True, autoincrement=True)
    
    # Bisa NULL, misal kalo login gagal karena email salah
    nid_user = Column(Integer, ForeignKey("tbls_users.nid"), nullable=True, index=True) 
    
    # Event: 'LOGIN_SUCCESS', 'LOGIN_FAILED', 'LOGOUT', 'PASSWORD_RESET_REQUEST', 
    # 'PASSWORD_RESET_SUCCESS', 'ACCOUNT_ACTIVATION', 'EMAIL_CHANGE_REQUEST', 'EMAIL_CHANGE_VERIFIED'
    vaction = Column(String(100), nullable=False, index=True)
    
    vip_address = Column(String(100), nullable=True)
    vuser_agent = Column(Text, nullable=True) # Info browser
    
    # Detail tambahan, misal: "reason: invalid password" atau "email: user@coba.com"
    vdetails = Column(Text, nullable=True) 
    
    dtimestamp = Column(DateTime, default=now_wib, index=True)

    # Relasi opsional buat gampang query
    user = relationship("User")