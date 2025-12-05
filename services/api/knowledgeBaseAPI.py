from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional

from ..schemas import knowledgeBaseSchema as schema, usersSchema
from ..controller import knowledgeBaseController, auditLogController, usersController, userAccessController
from ..database import SessionLocal

router = APIRouter(
    prefix="/knowledge-base",
    tags=["Knowledge Base"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_sa_only(db: Session, current_user: usersSchema.User):
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    
    if "SA" not in user_roles:
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya Super Admin yang boleh mengakses halaman ini."
        )

@router.get("/", response_model=schema.KnowledgeBaseResponse)
def read_all_knowledge_base(
    skip: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    vcategory: Optional[str] = None,
    vcontext: Optional[str] = None,
    vanswer: Optional[str] = None,
    status: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_sa_only(db, current_user)
    return knowledgeBaseController.get_all_knowledge_base(db, skip, limit, search, vcategory, vcontext, vanswer, status)

@router.get("/get-all/", response_model=List[schema.KnowledgeBase])
def read_all_knowledge_base_no_pagination(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_sa_only(db, current_user)
    return knowledgeBaseController.get_all_knowledge_base_no_pagination(db)

@router.get("/{nid}", response_model=schema.KnowledgeBase)
def read_knowledge_base_by_id(
    nid: int,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_sa_only(db, current_user)
    kb = knowledgeBaseController.get_knowledge_base_by_id(db, nid)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge Base not found")
    return kb

@router.post("/", response_model=schema.KnowledgeBase, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    data: schema.KnowledgeBaseCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_sa_only(db, current_user)
    new_kb = knowledgeBaseController.create_knowledge_base(db, data, current_user)
    
    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="CREATE",
        target_model="KnowledgeBase",
        target_identifier=str(new_kb.nid),
        jbefore=None,
        jafter=data.model_dump(),
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    return new_kb

@router.put("/{nid}", response_model=schema.KnowledgeBase)
def update_knowledge_base(
    nid: int,
    data: schema.KnowledgeBaseUpdate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_sa_only(db, current_user)
    
    # Get before state for log
    db_obj = knowledgeBaseController.get_knowledge_base_by_id(db, nid)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Knowledge Base not found")
    
    jbefore = schema.KnowledgeBase.model_validate(db_obj).model_dump(mode='json')
    
    updated_kb = knowledgeBaseController.update_knowledge_base(db, nid, data, current_user)
    
    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="UPDATE",
        target_model="KnowledgeBase",
        target_identifier=str(nid),
        jbefore=jbefore,
        jafter=data.model_dump(),
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    return updated_kb

@router.delete("/{nid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_base(
    nid: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_sa_only(db, current_user)
    
    # Get before state for log
    db_obj = knowledgeBaseController.get_knowledge_base_by_id(db, nid)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Knowledge Base not found")
    
    jbefore = schema.KnowledgeBase.model_validate(db_obj).model_dump(mode='json')
    
    knowledgeBaseController.delete_knowledge_base(db, nid, current_user)
    
    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="DELETE",
        target_model="KnowledgeBase",
        target_identifier=str(nid),
        jbefore=jbefore,
        jafter=None,
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    return
