from typing import List, Optional
from pydantic import BaseModel, EmailStr, field_validator, ValidationInfo
from datetime import datetime

class UserBase(BaseModel):
    vcode: str
    vname: str
    vemail: EmailStr
    vphone: Optional[str] = None
    vaddress: Optional[str] = None

class UserCreateByAdmin(UserBase):
    vcreated_by: str = "system"

class UserCreate(UserCreateByAdmin):
    vpassword: str

class UserRegister(UserBase):
    password: str
    confirm_password: str
    nid_department: int

    @field_validator('confirm_password') 
    @classmethod
    def passwords_match(cls, v: str, info: ValidationInfo) -> str:
        if 'password' in info.data and v != info.data['password']:
            raise ValueError('Password dan Konfirmasi Password tidak cocok')
        return v

class UserUpdate(UserBase):
    nstatus: int
    vmodified_by: str = "system"

class User(UserBase):
    nid: int
    nstatus: int
    dcreated_at: Optional[datetime] = None
    vcreated_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None

    class Config:
        from_attributes = True
        
class UserWithRoles(User): 
    roles: List[str] = []

class SetInitialPassword(BaseModel):
    token: str
    password: str
    
class ActivationToken(BaseModel):
    token: str

class UserResponse(BaseModel):
    data: List[User]
    total: int

class UserDropdown(BaseModel):
    nid: int
    vemail: str

    class Config:
        from_attributes = True

class UserDropdownResponse(BaseModel):
    data: List[UserDropdown]

class UserSafeResponse(BaseModel):
    vname: str
    vemail: EmailStr

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenData(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str 
    token_type: str
    user: User

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class NewAccessTokenResponse(BaseModel):
    access_token: str
    token_type: str

class RequestPasswordReset(BaseModel):
    email: EmailStr

class ResetPassword(BaseModel):
    token: str
    password: str