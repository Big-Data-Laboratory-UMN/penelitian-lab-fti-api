# services/schemas/bookingFilesSchema.py

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from .filesSchema import File as FilesSchema # Kita import schema File

# --- Schema dasar ---
# Ini data minimal yg kita butuh pas bikin relasi file
class BookingFileBase(BaseModel):
    vtype: str # 'proposal', 'documentation_image', 'documentation_article'
    nid_file: int # ID file yg udah diupload

# --- Schema untuk Buat Data (Create) ---
class BookingFileCreate(BookingFileBase):
    # nid_booking & vcreated_by bakal di-handle di controller
    pass

# --- Schema Lengkap (untuk Read/Response) ---
class BookingFileSchema(BookingFileBase):
    nid: int
    vcode: str
    nid_booking: int
    nstatus: int
    vcreated_by: str
    dcreated_at: datetime
    
    # Ini relasi buat nampilin detail file-nya (URL, vname, dll)
    file: Optional[FilesSchema] = None 

    class Config:
        from_attributes = True # Dulu orm_mode=True