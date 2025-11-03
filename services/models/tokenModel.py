from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    CheckConstraint
)
from sqlalchemy.sql import func
from ..database import Base
import pytz


def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

# Tipe Token: 1=Activation, 2=Login Session, 3=Password Reset, 4=Email Change
# Status Token: 1=Aktif, 0=Tidak Aktif

class Token(Base):
    __tablename__ = "tbls_token"

    nid = Column(Integer, primary_key=True, autoincrement=True)
    nid_user = Column(Integer, ForeignKey("tbls_users.nid"), nullable=False, comment="Foreign key ke tabel user (tbls_users)")
    
    ntoken_type = Column(Integer, nullable=False, index=True, comment="Tipe token: 1=Aktivasi, 2=Sesi Login, 3=Reset Password, 4=Ganti Email")
    
    vcode = Column(String(255), unique=True, index=True, nullable=False, comment="Kode unik untuk token aktivasi atau password reset")
    vnew_email = Column(String(255), nullable=True, comment="Email baru yang menunggu verifikasi") 
    vaccess_token = Column(Text, nullable=True, comment="JWT access token untuk sesi login") 
    vrefresh_token = Column(Text, nullable=True, comment="JWT refresh token untuk memperbarui access token")
    vbrowser_info = Column(Text, nullable=True, comment="Informasi browser/User-Agent dari user")
    vip_address = Column(String(50), nullable=True, comment="Alamat IP user saat request token")
    dexpires_at = Column(DateTime(timezone=True), nullable=False, comment="Waktu kedaluwarsa untuk token aktivasi atau access token")
    drefresh_expire_at = Column(DateTime(timezone=True), nullable=True, comment="Waktu kedaluwarsa untuk refresh token")
    
    nstatus = Column(Integer, nullable=False, default=1, comment="Status token: 1=Aktif, 0=Tidak Aktif/Sudah digunakan")
    
    dcreated_at = Column(DateTime(timezone=True), default=now_wib, nullable=False)
    dmodified_at = Column(DateTime(timezone=True), onupdate=now_wib, nullable=True)

    __table_args__ = (
        CheckConstraint(ntoken_type.in_([1, 2, 3, 4]), name='chk_token_type_values'),
        CheckConstraint(nstatus.in_([0, 1]), name='chk_token_nstatus_values')
    )