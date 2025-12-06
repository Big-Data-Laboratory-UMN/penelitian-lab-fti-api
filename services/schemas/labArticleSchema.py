# services/schemas/labArticleSchema.py

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


class ArticleTagBase(BaseModel):
    vtag: str = Field(..., max_length=100)


class ArticleTagCreate(ArticleTagBase):
    pass


class ArticleTagSchema(ArticleTagBase):
    nid: int
    nid_article: int

    class Config:
        from_attributes = True


class LabArticleBase(BaseModel):
    nid_lab: int
    vtitle: str = Field(..., max_length=50)
    vexcerpt: Optional[str] = Field(None, max_length=500)
    vcontent: str = Field(..., max_length=100000)
    vthumbnail: Optional[str] = Field(None, max_length=500)
    nis_featured: Optional[int] = 0
    dpublished_at: Optional[datetime] = None
    tags: Optional[List[str]] = Field(default_factory=list, max_length=5)
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        if v and len(v) > 5:
            raise ValueError('Maximum 5 tags allowed per article')
        return v
    
    @field_validator('nis_featured')
    @classmethod
    def validate_featured(cls, v):
        if v not in [0, 1]:
            raise ValueError('nis_featured must be 0 or 1')
        return v


class LabArticleCreate(LabArticleBase):
    vcreated_by: Optional[str] = None


class LabArticleUpdate(BaseModel):
    nid_lab: Optional[int] = None
    vtitle: Optional[str] = Field(None, max_length=50)
    vexcerpt: Optional[str] = Field(None, max_length=500)
    vcontent: Optional[str] = Field(None, max_length=100000)
    vthumbnail: Optional[str] = Field(None, max_length=500)
    nis_featured: Optional[int] = None
    nstatus: Optional[int] = None
    dpublished_at: Optional[datetime] = None
    tags: Optional[List[str]] = None
    vmodified_by: Optional[str] = None
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        if v and len(v) > 5:
            raise ValueError('Maximum 5 tags allowed per article')
        return v
    
    @field_validator('nis_featured', 'nstatus')
    @classmethod
    def validate_status_fields(cls, v, info):
        if v is not None:
            if info.field_name == 'nis_featured' and v not in [0, 1]:
                raise ValueError('nis_featured must be 0 or 1')
            if info.field_name == 'nstatus' and v not in [0, 1, 2]:
                raise ValueError('nstatus must be 0 (Inactive), 1 (Published), or 2 (Scheduled)')
        return v


class LabArticleSchema(BaseModel):
    nid: int
    vcode: str
    nid_lab: int
    nid_user: int
    
    vtitle: str
    vexcerpt: Optional[str] = None
    vcontent: str
    vthumbnail: Optional[str] = None
    
    nis_featured: int
    nstatus: int
    dpublished_at: Optional[datetime] = None
    
    dcreated_at: datetime
    vcreated_by: Optional[str] = None
    dmodified_at: Optional[datetime] = None
    vmodified_by: Optional[str] = None
    
    # Joined fields for display
    lab_name: Optional[str] = None
    author_name: Optional[str] = None
    tags: List[ArticleTagSchema] = []

    class Config:
        from_attributes = True


class LabArticlePublicSchema(BaseModel):
    """Simplified schema for public display"""
    vcode: str
    vtitle: str
    vexcerpt: Optional[str] = None
    vthumbnail: Optional[str] = None
    dpublished_at: Optional[datetime] = None
    lab_name: Optional[str] = None
    lab_code: Optional[str] = None
    author_name: Optional[str] = None
    tags: List[str] = []
    nis_featured: int = 0

    class Config:
        from_attributes = True


class LabArticleDetailSchema(LabArticlePublicSchema):
    """Full article detail for public display"""
    vcontent: str


class LabArticleResponse(BaseModel):
    data: List[LabArticleSchema]
    total: int


class LabArticlePublicResponse(BaseModel):
    data: List[LabArticlePublicSchema]
    total: int


class LabArticleDropdown(BaseModel):
    nid: int
    vtitle: str
    vcode: str

    class Config:
        from_attributes = True


class LabArticleDropdownResponse(BaseModel):
    data: List[LabArticleDropdown]
