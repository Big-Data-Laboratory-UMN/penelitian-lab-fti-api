from typing import List, Optional # Optional masih dipakai
from pydantic import BaseModel
from datetime import datetime

from .filesSchema import File as FilesSchema

class FacilityCreate(BaseModel):
    """
    Schema untuk membuat data Facility baru.
    File dihandle terpisah di API.
    """
    vcode: str
    vname: str
    vdesc: str
    vcreated_by: str = "system" # Bisa di-override di API dengan user login
    nid_lab: Optional[int] = None # [OPTIONAL] Jika diisi, otomatis mapping ke lab ini

class FacilityUpdate(BaseModel):
    """
    Schema untuk mengupdate data Facility.
    Update file (mengganti nid_file) bisa dilakukan di sini.
    """
    vcode: str # Pertimbangkan apakah vcode boleh diubah
    vname: str
    vdesc: str
    nstatus: int
    nid_file: Optional[int] = None # Untuk mengubah file yang terhubung (bisa jadi None)
    vmodified_by: str = "system" # Bisa di-override di API dengan user login

class Facility(BaseModel):
    """
    Schema dasar untuk data Facility, termasuk info file terkait (opsional).
    """
    nid: int
    vcode: str
    vname: str
    vdesc: str
    nstatus: int
    nid_file: Optional[int] = None # ID file yang terhubung (jika ada)
    dcreated_at: Optional[datetime] = None
    vcreated_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None

    # Menampilkan detail file yang terhubung (jika ada)
    related_file: Optional[FilesSchema] = None

    class Config:
        from_attributes = True # Untuk compatibility dengan objek ORM

class FacilityResponse(BaseModel):
    """
    Schema untuk response list data Facility dengan paginasi.
    """
    data: List[Facility] # List dari schema Facility (yang sudah termasuk related_file)
    total: int

class FacilityDropdown(BaseModel):
    """
    Schema sederhana untuk kebutuhan dropdown Facility.
    """
    nid: int
    vname: str # Nama fasilitas untuk display

    class Config:
        from_attributes = True

class FacilityDropdownResponse(BaseModel):
    """
    Schema untuk response list data dropdown Facility.
    """
    data: List[FacilityDropdown]