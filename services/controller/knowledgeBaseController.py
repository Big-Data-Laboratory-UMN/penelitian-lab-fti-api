from sqlalchemy.orm import Session
from sqlalchemy import or_
from ..models import KnowledgeBaseModel as models
from ..schemas import knowledgeBaseSchema as schema, usersSchema
from . import chatbotController
from datetime import datetime
import pytz

def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

def get_all_knowledge_base(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    category: str | None = None,
    nstatus: int | None = None
):
    query = db.query(models.knowledge_base)

    if nstatus is not None:
        query = query.filter(models.knowledge_base.nstatus == nstatus)

    if search:
        search_filter = or_(
            models.knowledge_base.vcontext.ilike(f"%{search}%"),
            models.knowledge_base.vanswer.ilike(f"%{search}%"),
            models.knowledge_base.vcategory.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    if category:
        query = query.filter(models.knowledge_base.vcategory.ilike(f"%{category}%"))

    total = query.count()
    
    # Default sort by dsort_at desc (newest modified/created first)
    query = query.order_by(models.knowledge_base.dsort_at.desc())
    
    data = query.offset(skip).limit(limit).all()

    return {"data": data, "total": total}

def get_all_knowledge_base_no_pagination(db: Session):
    return db.query(models.knowledge_base).order_by(models.knowledge_base.dsort_at.desc()).all()

def get_knowledge_base_by_id(db: Session, nid: int):
    return db.query(models.knowledge_base).filter(models.knowledge_base.nid == nid).first()

def create_knowledge_base(db: Session, data: schema.KnowledgeBaseCreate, current_user: usersSchema.User):
    db_obj = models.knowledge_base(**data.model_dump())
    db_obj.vcreated_by = current_user.vcode
    db_obj.dsort_at = now_wib()
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    
    # Reload Chatbot KB
    try:
        chatbotController.load_kb()
    except Exception as e:
        print(f"[WARNING] Failed to reload Chatbot KB: {e}")
        
    return db_obj

def update_knowledge_base(db: Session, nid: int, data: schema.KnowledgeBaseUpdate, current_user: usersSchema.User):
    db_obj = get_knowledge_base_by_id(db, nid)
    if not db_obj:
        return None
    
    db_obj.vcategory = data.vcategory
    db_obj.vcontext = data.vcontext
    db_obj.vanswer = data.vanswer
    db_obj.nstatus = data.nstatus
    db_obj.vmodified_by = current_user.vcode
    db_obj.dsort_at = now_wib()
    
    db.commit()
    db.refresh(db_obj)
    
    # Reload Chatbot KB
    try:
        chatbotController.load_kb()
    except Exception as e:
        print(f"[WARNING] Failed to reload Chatbot KB: {e}")

    return db_obj

def delete_knowledge_base(db: Session, nid: int, current_user: usersSchema.User):
    db_obj = get_knowledge_base_by_id(db, nid)
    if db_obj:
        db_obj.nstatus = 0 # Soft Delete
        db_obj.vmodified_by = current_user.vcode
        db_obj.dsort_at = now_wib()
        db.commit()
        db.refresh(db_obj)
        
        # Reload Chatbot KB
        try:
            chatbotController.load_kb()
        except Exception as e:
            print(f"[WARNING] Failed to reload Chatbot KB: {e}")
            
    return db_obj
