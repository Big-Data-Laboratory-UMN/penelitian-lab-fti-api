# services/api/labArticleAPI.py

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, List
import json

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
    nid_user: Optional[int] = None,
    nstatus: Optional[int] = None,
    nis_featured: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
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
        nid_user=nid_user,
        nstatus=nstatus,
        nis_featured=nis_featured,
        start_date=start_date,
        end_date=end_date
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
async def create_new_article(
    request: Request,
    background_tasks: BackgroundTasks,
    nid_lab: int = Form(...),
    vtitle: str = Form(...),
    vexcerpt: Optional[str] = Form(None),
    vcontent: str = Form(...),
    nis_featured: Optional[int] = Form(0),
    dpublished_at: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # JSON string of array
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Create new article with optional thumbnail image"""
    check_forbidden_roles(db, current_user)
    
    try:
        # Parse tags from JSON string
        parsed_tags = []
        if tags:
            try:
                parsed_tags = json.loads(tags)
            except:
                parsed_tags = []
        
        # Parse dpublished_at if provided
        from datetime import datetime
        parsed_date = None
        if dpublished_at:
            try:
                parsed_date = datetime.fromisoformat(dpublished_at.replace('Z', '+00:00'))
            except:
                parsed_date = None
        
        # Build article schema
        article = schema.LabArticleCreate(
            nid_lab=nid_lab,
            vtitle=vtitle,
            vexcerpt=vexcerpt,
            vcontent=vcontent,
            nis_featured=nis_featured,
            dpublished_at=parsed_date,
            tags=parsed_tags,
            vcreated_by=current_user.vcode
        )
        
        new_article = await labArticleController.create_article_with_file(
            db=db,
            article=article,
            file=file,
            current_user=current_user,
            request=request
        )
        
        # If article is scheduled (nstatus=2), add precise scheduling job
        if new_article.nstatus == 2 and new_article.dpublished_at:
            scheduler = request.app.state.scheduler if hasattr(request.app.state, 'scheduler') else None
            if scheduler and scheduler.running:
                labArticleController.schedule_article_publish(
                    scheduler=scheduler,
                    db_factory=SessionLocal,
                    article_vcode=new_article.vcode,
                    publish_datetime=new_article.dpublished_at
                )
        
        # Activity Log
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="CREATE",
            target_model="LabArticle",
            target_identifier=new_article.vcode,
            jbefore=None,
            jafter=article.model_dump(mode='json'),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        
        return new_article
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        print(f"Error creating article: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.put("/{vcode}", response_model=schema.LabArticleSchema)
async def update_existing_article(
    vcode: str,
    request: Request,
    background_tasks: BackgroundTasks,
    nid_lab: Optional[int] = Form(None),
    vtitle: Optional[str] = Form(None),
    vexcerpt: Optional[str] = Form(None),
    vcontent: Optional[str] = Form(None),
    nis_featured: Optional[int] = Form(None),
    nstatus: Optional[int] = Form(None),
    dpublished_at: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # JSON string of array
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Update existing article with optional thumbnail image"""
    check_forbidden_roles(db, current_user)
    
    # Get before state for logging
    db_article_before = labArticleController.get_article_by_code(db, vcode=vcode)
    if not db_article_before:
        raise HTTPException(status_code=404, detail="Article not found")
    
    jbefore = schema.LabArticleSchema.model_validate(db_article_before).model_dump(mode='json')
    
    try:
        # Parse tags from JSON string
        parsed_tags = None
        if tags is not None:
            try:
                parsed_tags = json.loads(tags)
            except:
                parsed_tags = None
        
        # Parse dpublished_at if provided
        from datetime import datetime
        parsed_date = None
        if dpublished_at:
            try:
                parsed_date = datetime.fromisoformat(dpublished_at.replace('Z', '+00:00'))
            except:
                parsed_date = None
        
        # Build article update schema
        article = schema.LabArticleUpdate(
            nid_lab=nid_lab,
            vtitle=vtitle,
            vexcerpt=vexcerpt,
            vcontent=vcontent,
            nis_featured=nis_featured,
            nstatus=nstatus,
            dpublished_at=parsed_date,
            tags=parsed_tags,
            vmodified_by=current_user.vcode
        )
        
        db_article = await labArticleController.update_article_with_file(
            db=db,
            vcode=vcode,
            article=article,
            file=file,
            current_user=current_user,
            request=request
        )
        
        # Activity Log
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="UPDATE",
            target_model="LabArticle",
            target_identifier=db_article.vcode,
            jbefore=jbefore,
            jafter=article.model_dump(mode='json'),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        
        return db_article
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        print(f"Error updating article: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


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
        "nid_file": article.nid_file,
        "related_file": article.related_file,
        "dpublished_at": article.dpublished_at,
        "lab_name": result["lab_name"],
        "lab_code": result["lab_code"],
        "author_name": result["author_name"],
        "tags": result["tags"],
        "nis_featured": article.nis_featured
    }


@router.get("/public/{vcode}/related")
def get_public_related_articles(
    vcode: str,
    limit: int = 3,
    db: Session = Depends(get_db)
):
    """
    Get related articles for a given article.
    Priority: Tag matching, then same lab.
    """
    return labArticleController.get_related_articles(db=db, vcode=vcode, limit=limit)
