from sqlalchemy import Column, Integer, DateTime, ForeignKey, func, String
from sqlalchemy.orm import relationship
from ..database import Base 
from datetime import datetime
import pytz


def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

class BookingFile(Base):
    __tablename__ = 'tblr_booking_files' 

    nid = Column(Integer, primary_key=True, autoincrement=True)
    vcode = Column(String(100), unique=True, index=True, nullable=False) 
    nid_booking = Column(Integer, ForeignKey('tblt_booking.nid'), nullable=False) 
    # Ini nyambung ke file yang di-upload (di tabel files)
    nid_file = Column(Integer, ForeignKey('tblm_files.nid'), nullable=False) 
    
    # Ini buat nandain dia file apa: 'proposal', 'documentation_image', 'documentation_article'
    vtype = Column(String(50), nullable=False, index=True) 

    # --- Standar Kolom ---
    nstatus = Column(Integer, nullable=False, default=1) # 1 = Active, 0 = Inactive (soft delete)
    
    dcreated_at = Column(DateTime, default=now_wib)
    vcreated_by = Column(String(100), nullable=True)
    dmodified_at = Column(DateTime, onupdate=now_wib)
    vmodified_by = Column(String(100), nullable=True)
    
    dsort_at = Column(DateTime, default=now_wib, onupdate=now_wib)

    # --- Relationships ---
    # Relasi balik ke Booking (Banyak file dimiliki 1 booking)
    booking = relationship("Booking", back_populates="booking_files")
    
    # Relasi ke File (1 row ini punya 1 data file)
    # Kita bikin 1 arah aja, tabel File gausah tau dia dipake di booking mana
    file = relationship("Files")