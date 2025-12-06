# services/api/labArticleAPI.py

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List

from ..schemas import labArticleSchema as schema, usersSchema, labSchema
from ..controller import labArticleController, usersController, userAccessController, auditLogController
from ..database import SessionLocal

router = APIRouter(
    prefix="/lab-article",
    tags=["Lab Articles"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_forbidden_roles(db: Session, current_user: usersSchema.User):
    """Block Visitor role from accessing admin endpoints"""
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if "VSTR" in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk operasi ini."
        )


# --- ADMIN ENDPOINTS (Authenticated + Scoped) ---

@router.get("/", response_model=schema.LabArticleResponse)
def read_all_articles(
    skip: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    nid_lab: Optional[int] = None,
    nstatus: Optional[int] = None,
    nis_featured: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Get all articles with scoping based on user role"""
    check_forbidden_roles(db, current_user)
    articles_data = labArticleController.get_articles(
        db=db,
        current_user=current_user,
        skip=skip,
        limit=limit,
        search=search,
        nid_lab=nid_lab,
        nstatus=nstatus,
        nis_featured=nis_featured
    )
    return articles_data


@router.get("/scoped-labs-dropdown/", response_model=labSchema.LabDropdownResponse)
def get_scoped_labs_for_article_create(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Get labs the current user can create/edit articles for.
    SA: All labs, ADM: Department labs, PIC: Assigned labs
    """
    check_forbidden_roles(db, current_user)
    labs_data = labArticleController.get_scoped_labs_for_article(db=db, current_user=current_user)
    return labs_data


@router.get("/{vcode}", response_model=schema.LabArticleSchema)
def get_article_by_code(
    vcode: str,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Get single article by code (admin)"""
    check_forbidden_roles(db, current_user)
    article = labArticleController.get_article_by_code(db=db, vcode=vcode)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # Check access
    if not labArticleController.check_lab_access(db, current_user, article.nid_lab):
        raise HTTPException(status_code=403, detail="You don't have access to this article")
    
    return article


@router.post("/", response_model=schema.LabArticleSchema, status_code=status.HTTP_201_CREATED)
def create_new_article(
    article: schema.LabArticleCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Create new article"""
    check_forbidden_roles(db, current_user)
    
    try:
        article.vcreated_by = current_user.vcode
        new_article = labArticleController.create_article(
            db=db,
            article=article,
            current_user=current_user
        )
        
        # Activity Log
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="CREATE",
            target_model="LabArticle",
            target_identifier=new_article.vcode,
            jbefore=None,
            jafter=article.model_dump(),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        
        return new_article
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.put("/{vcode}", response_model=schema.LabArticleSchema)
def update_existing_article(
    vcode: str,
    article: schema.LabArticleUpdate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Update existing article"""
    check_forbidden_roles(db, current_user)
    
    # Get before state for logging
    db_article_before = labArticleController.get_article_by_code(db, vcode=vcode)
    if not db_article_before:
        raise HTTPException(status_code=404, detail="Article not found")
    
    jbefore = schema.LabArticleSchema.model_validate(db_article_before).model_dump(mode='json')
    
    try:
        article.vmodified_by = current_user.vcode
        db_article = labArticleController.update_article(
            db=db,
            vcode=vcode,
            article=article,
            current_user=current_user
        )
        
        # Activity Log
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="UPDATE",
            target_model="LabArticle",
            target_identifier=db_article.vcode,
            jbefore=jbefore,
            jafter=article.model_dump(),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        
        return db_article
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.delete("/{vcode}", status_code=status.HTTP_204_NO_CONTENT)
def delete_article(
    vcode: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Soft delete article (set nstatus=0)"""
    check_forbidden_roles(db, current_user)
    
    db_article_before = labArticleController.get_article_by_code(db, vcode=vcode)
    if not db_article_before:
        raise HTTPException(status_code=404, detail="Article not found")
    
    jbefore = schema.LabArticleSchema.model_validate(db_article_before).model_dump(mode='json')
    
    try:
        deleted_article = labArticleController.delete_article(
            db=db,
            vcode=vcode,
            current_user=current_user
        )
        
        # Activity Log
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="DELETE",
            target_model="LabArticle",
            target_identifier=vcode,
            jbefore=jbefore,
            jafter={"nstatus": 0},
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        
        return
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


# --- PUBLIC ENDPOINTS (No Auth) ---

@router.get("/public/all", response_model=schema.LabArticlePublicResponse)
def get_public_articles(
    skip: int = 0,
    limit: int = 20,
    lab_code: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get all published articles for public display (no auth required).
    Only returns active articles (nstatus=1).
    """
    articles_data = labArticleController.get_public_articles(
        db=db,
        skip=skip,
        limit=limit,
        lab_code=lab_code,
        search=search
    )
    return articles_data


@router.get("/public/{vcode}", response_model=schema.LabArticleDetailSchema)
def get_public_article_detail(
    vcode: str,
    db: Session = Depends(get_db)
):
    """
    Get single article detail for public display (no auth required).
    Only returns active articles (nstatus=1).
    """
    result = labArticleController.get_article_by_code_public(db=db, vcode=vcode)
    if not result:
        raise HTTPException(status_code=404, detail="Article not found")
    
    article = result["article"]
    return {
        "vcode": article.vcode,
        "vtitle": article.vtitle,
        "vexcerpt": article.vexcerpt,
        "vcontent": article.vcontent,
        "vthumbnail": article.vthumbnail,
        "dpublished_at": article.dpublished_at,
        "lab_name": result["lab_name"],
        "lab_code": result["lab_code"],
        "author_name": result["author_name"],
        "tags": result["tags"],
        "nis_featured": article.nis_featured
    }
