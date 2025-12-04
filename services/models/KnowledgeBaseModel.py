from sqlalchemy import Column, Integer, Text, String, DateTime
from services.database import Base
from datetime import datetime

class knowledge_base(Base):
    __tablename__ = "tblm_knowledge_base"

    nid = Column(Integer, primary_key=True, autoincrement=True)
    vcategory=Column(String(255), nullable=True)
    vcontext=Column(Text, nullable=True)
    vanswer=Column(Text, nullable=True)