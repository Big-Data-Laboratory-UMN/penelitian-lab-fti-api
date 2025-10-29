# services/schemas/bookingSchema.py

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from .bookingFilesSchema import BookingFileSchema # Import schema file yg baru dibuat
from .usersSchema import User as UserSchema # Import schema user
from .labFacilitySchema import FacilityLab as LabFacilitySchema # Import schema lab-facility

# --- Schema dasar (Input pas Create) ---
# Ini data yg diisi user di form
class BookingBase(BaseModel):
    nid_lab_facility: int # ID dari lab/fasilitas yg dipilih
    dstart: datetime
    dend: datetime
    vactivity: str # Deskripsi/Aktivitas yg ditanya tadi

# --- Schema untuk Buat Data (Create) ---
# Ini adalah payload API pas user klik "Submit"
class BookingCreate(BookingBase):
    # User WAJIB ngasih ID file proposal yg udah di-upload duluan
    nid_proposal_file: int 

# --- Schema untuk Update Data ---
# Ini dipake pas Admin (approve/reject) ATAU User (upload doc)
class BookingUpdate(BaseModel):
    nstatus: Optional[int] = None # Buat ganti status (approve, reject, done, etc)
    
    # Buat user upload dokumentasi akhir (file-nya udah diupload, kirim ID-nya)
    nid_documentation_images: Optional[List[int]] = None
    nid_documentation_article: Optional[int] = None

# --- Schema Lengkap (untuk Read/Response) ---
# Ini data LENGKAP yg dikirim API ke frontend
class BookingSchema(BookingBase):
    nid: int
    vcode: str
    nid_user: int
    nstatus: int # Status (0, 1, 2, 3, 4, 5)

    vcreated_by: str
    dcreated_at: datetime
    vmodified_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None

    # --- Relasi (Data Tambahan) ---
    # Data user yg booking
    user: Optional[UserSchema] = None 
    # Data lab/fasilitas yg dibooking
    lab_facility: Optional[LabFacilitySchema] = None 
    # List semua file yg nyangkut di booking ini (proposal, image, article)
    booking_files: List[BookingFileSchema] = [] 

    class Config:
        from_attributes = True # Wajib ada

# --- Schema untuk List Response (Pagination) ---
class BookingResponse(BaseModel):
    data: List[BookingSchema]
    total: int