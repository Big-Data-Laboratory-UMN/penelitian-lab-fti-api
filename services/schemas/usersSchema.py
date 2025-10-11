from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime

class UserBase(BaseModel):
    """
    Berisi field-field paling dasar dari seorang user yang sering muncul di banyak tempat.
    """
    vcode: str
    vname: str
    vemail: EmailStr
    vphone: Optional[str] = None
    vaddress: Optional[str] = None
    vinstitution: Optional[str] = None

class UserCreateByAdmin(UserBase):
    """
    Schema untuk Admin membuat user. Mewarisi semua field dari UserBase.
    Cukup tambahkan field spesifik untuk proses ini.
    """
    vcreated_by: str = "system"

class UserCreate(UserCreateByAdmin):
    """
    Schema untuk user mendaftar sendiri.
    Mewarisi semua field dari UserCreateByAdmin (yang juga mewarisi UserBase),
    lalu kita tambahkan field password.
    """
    vpassword: str

class UserUpdate(UserBase):
    """
    Schema untuk update user. Mewarisi field dasar, lalu tambah field spesifik.
    """
    nstatus: int
    vmodified_by: str = "system"

class User(UserBase):
    """

    Schema lengkap untuk data user yang dikirim sebagai response dari API.
    """
    nid: int
    nstatus: int
    dcreated_at: Optional[datetime] = None
    vcreated_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None

    class Config:
        from_attributes = True

class SetInitialPassword(BaseModel):
    token: str
    password: str

class UserResponse(BaseModel):
    data: List[User]
    total: int

class UserDropdown(BaseModel):
    nid: int
    vname: str

    class Config:
        from_attributes = True

class UserDropdownResponse(BaseModel):
    data: List[UserDropdown]