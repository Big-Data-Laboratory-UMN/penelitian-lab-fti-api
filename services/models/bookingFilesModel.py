from sqlalchemy import Column, Integer, DateTime, ForeignKey, func, String
from sqlalchemy.orm import relationship
from ..database import Base 
from datetime import datetime

class BookingFile(Base):
    __tablename__ = 'tblr_booking_files' 

    nid = Column(Integer, primary_key=True, autoincrement=True)
    vcode = Column(String(100), unique=True, index=True, nullable=False) 
    nid_booking = Column(Integer, ForeignKey('tblt_booking.nid'), nullable=False) 
    # Ini nyambung ke file yang di-upload (di tabel files)
    nid_file = Column(Integer, ForeignKey('tblm_files.nid'), nullable=False) 
    
    # --- Tipe File (PENTING) ---
    # Ini buat nandain dia file apa: 'proposal', 'documentation_image', 'documentation_article'
    vtype = Column(String(50), nullable=False, index=True) 

    # --- Standar Kolom ---
    nstatus = Column(Integer, nullable=False, default=1) # 1 = Active, 0 = Inactive (soft delete)
    vcreated_by = Column(String(255), nullable=False) 
    vmodified_by = Column(String(255), nullable=True)
    dcreated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    dmodified_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    dsort_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) 

    # --- Relationships ---
    # Relasi balik ke Booking (Banyak file dimiliki 1 booking)
    booking = relationship("Booking", back_populates="booking_files")
    
    # Relasi ke File (1 row ini punya 1 data file)
    # Kita bikin 1 arah aja, tabel File gausah tau dia dipake di booking mana
    file = relationship("Files")