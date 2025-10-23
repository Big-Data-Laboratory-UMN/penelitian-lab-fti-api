from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class FileCreate(BaseModel):
    """
    Schema untuk membuat data File baru.
    """
    vcode: str
    vname: str
    vtype: str # Tipe MIME file, misal 'image/jpeg', 'application/pdf'
    vpath: str # Path penyimpanan di server atau URL cloud storage
    vextension: str # Ekstensi file, misal '.jpg', '.pdf'
    nsize: float # Ukuran file dalam bytes (atau unit lain, sesuaikan)
    vcategory: str # Kategori file, misal 'gambar_fasilitas', 'dokumen_lab'
    nis_public: int = 1 # Default 1 (public), bisa 0 (private)
    # nstatus defaultnya 1 di model, jadi gak perlu di create schema
    vcreated_by: str = "system"

class FileUpdate(BaseModel):
    """
    Schema untuk mengupdate data File.
    Biasanya path tidak diupdate langsung di sini, tapi dihandle terpisah jika file diganti.
    """
    vcode: str # Mungkin vcode tidak boleh diubah? Tergantung logic bisnis
    vname: str
    vtype: str
    vpath: str # Update path jika file dipindah/diganti
    vextension: str
    nsize: float
    vcategory: str
    nis_public: int
    nstatus: int
    vmodified_by: str = "system"

class File(BaseModel):
    """
    Schema dasar untuk data File (response).
    """
    nid: int
    vcode: str
    vname: str
    vtype: str
    vpath: str
    vextension: str
    nsize: float
    vcategory: str
    nis_public: int
    nstatus: int
    dcreated_at: Optional[datetime] = None
    vcreated_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None

    class Config:
        from_attributes = True # Mengizinkan Pydantic membaca dari atribut objek ORM

class FileResponse(BaseModel):
    """
    Schema untuk response list data File dengan paginasi.
    """
    data: List[File]
    total: int

class FileDropdown(BaseModel):
    """
    Schema sederhana untuk kebutuhan dropdown File.
    """
    nid: int
    vname: str # Tampilkan nama file di dropdown

    class Config:
        from_attributes = True

class FileDropdownResponse(BaseModel):
    """
    Schema untuk response list data dropdown File.
    """
    data: List[FileDropdown]