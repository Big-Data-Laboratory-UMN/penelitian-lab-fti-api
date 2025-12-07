# services/schemas/landingPageSchema.py

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# --- File Schema for nested display ---
class SlideFile(BaseModel):
    """Schema for file data in slide responses"""
    nid: int
    vcode: str
    vname: str
    vpath: Optional[str] = None

    class Config:
        from_attributes = True


# --- Slide Schemas ---
class LandingPageSlideBase(BaseModel):
    vheader: Optional[str] = Field(None, max_length=255)
    vsubtext: Optional[str] = None


class LandingPageSlideUpdate(LandingPageSlideBase):
    nid_file: Optional[int] = None
    nstatus: Optional[int] = None
    vmodified_by: Optional[str] = None


class LandingPageSlideSchema(BaseModel):
    nid: int
    vcode: str
    norder: int
    vheader: Optional[str] = None
    vsubtext: Optional[str] = None
    nid_file: Optional[int] = None
    related_file: Optional[SlideFile] = None
    nstatus: Optional[int] = 1
    dcreated_at: datetime
    vcreated_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None

    class Config:
        from_attributes = True


# --- Content Schemas ---
class LandingPageContentBase(BaseModel):
    vabout_header: Optional[str] = Field(None, max_length=255)
    vabout_subtext: Optional[str] = None


class LandingPageContentUpdate(LandingPageContentBase):
    vmodified_by: Optional[str] = None


class LandingPageContentSchema(BaseModel):
    nid: int
    vcode: str
    vabout_header: Optional[str] = None
    vabout_subtext: Optional[str] = None
    dcreated_at: datetime
    vcreated_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None
    slides: List[LandingPageSlideSchema] = []

    class Config:
        from_attributes = True


# --- Public Schema (for anonymous access) ---
class LandingPageSlidePublic(BaseModel):
    norder: int
    vheader: Optional[str] = None
    vsubtext: Optional[str] = None
    image_url: Optional[str] = None  # Will be computed from file

    class Config:
        from_attributes = True


class LandingPagePublicSchema(BaseModel):
    vabout_header: Optional[str] = None
    vabout_subtext: Optional[str] = None
    slides: List[LandingPageSlidePublic] = []

    class Config:
        from_attributes = True


# --- Response Schemas ---
class LandingPageResponse(BaseModel):
    data: LandingPageContentSchema
    message: str = "Success"


class LandingPageSlidesResponse(BaseModel):
    data: List[LandingPageSlideSchema]
    message: str = "Success"


class LandingPagePublicResponse(BaseModel):
    data: LandingPagePublicSchema
    message: str = "Success"
