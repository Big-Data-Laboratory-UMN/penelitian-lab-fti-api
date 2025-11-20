from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from .usersSchema import User # Kita butuh detail user

# --- SHARED ---
# Base schema biar gak redundan
class ActorInfo(BaseModel):
    nid: int
    vname: str
    vemail: str
    vrole: Optional[str] = None

# --- ACTIVITY LOG (Tracking Perubahan Data) ---
class ActivityLogResponse(BaseModel):
    nid: int
    # Flatten user info biar FE gak perlu gali deep object
    actor_name: str 
    actor_email: str
    actor_role: Optional[str] = None
    
    action: str = Field(..., alias="vaction") # CREATE, UPDATE, DELETE
    module: str = Field(..., alias="vtarget_model") # e.g. Booking, Lab
    target_id: str = Field(..., alias="vtarget_identifier") # ID objek yg diubah
    
    # Data changes (Crucial buat table diff)
    changes_before: Optional[Dict[str, Any]] = Field(None, alias="jbefore")
    changes_after: Optional[Dict[str, Any]] = Field(None, alias="jafter")
    
    ip_address: Optional[str] = Field(None, alias="vip_address")
    timestamp: datetime = Field(..., alias="dtimestamp")

    class Config:
        from_attributes = True
        populate_by_name = True # Biar bisa pake alias

# --- SECURITY LOG (Tracking Login/Access) ---
class SecurityLogResponse(BaseModel):
    nid: int
    actor_name: Optional[str] = "System/Guest"
    actor_email: Optional[str] = None
    
    event: str = Field(..., alias="vaction") # LOGIN_SUCCESS, LOGIN_FAILED
    status: str = "Info" # Computed field di FE nanti (Success=Green, Failed=Red)
    
    ip_address: Optional[str] = Field(None, alias="vip_address")
    device_info: Optional[str] = Field(None, alias="vuser_agent") 
    details: Optional[str] = Field(None, alias="vdetails")
    
    timestamp: datetime = Field(..., alias="dtimestamp")

    class Config:
        from_attributes = True
        populate_by_name = True

# --- STATS SCHEMA (INI YANG TADI HILANG) ---
class AuditStats(BaseModel):
    # Activity Stats
    total_activities: int
    creates: int
    updates: int
    deletes: int
    
    # Security Stats
    total_security_events: int
    login_success: int
    failed_logins: int
    
    # User Insight
    unique_actors: int
    distinct_ips: int
    
    # Info tambahan (Opsional, buat ngasih tau FE ini data rentang kapan)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    
# --- PAGINATION WRAPPER ---
class PaginatedActivityLog(BaseModel):
    data: List[ActivityLogResponse]
    total: int
    page: int
    limit: int

class PaginatedSecurityLog(BaseModel):
    data: List[SecurityLogResponse]
    total: int
    page: int
    limit: int

class DistributionItem(BaseModel):
    label: str
    value: int

class DistributionResponse(BaseModel):
    activity: List[DistributionItem] 
    security: List[DistributionItem]
    
    # Opsional: Info range tanggal
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None