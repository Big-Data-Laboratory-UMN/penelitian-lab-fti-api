# services/controller/labArticleController.py

from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List, Set
import uuid
from datetime import datetime
import pytz

from ..models import labArticleModel as models
from ..models import userAccessModel, rolesModel, departmentLabModel, labModel, usersModel
from ..schemas import labArticleSchema as schema
from ..schemas import usersSchema


def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))


def generate_article_code():
    """Generate unique article code"""
    return f"ART-{uuid.uuid4().hex[:8].upper()}"


# --- SCOPE LOGIC HELPERS ---

def _get_user_scope_info(db: Session, current_user: usersSchema.User):
    """
    Returns: (is_global, allowed_lab_ids)
    - SA: is_global=True, labs don't matter
    - ADM: is_global=False, labs from their departments
    - PIC: is_global=False, only assigned labs
    """
    admin_accesses = db.query(userAccessModel.UserAccess).join(
        rolesModel.Role, userAccessModel.UserAccess.nid_role == rolesModel.Role.nid
    ).filter(
        userAccessModel.UserAccess.nid_user == current_user.nid,
        userAccessModel.UserAccess.nstatus == 1
    ).all()

    is_global = False
    allowed_dept_ids = set()
    allowed_lab_ids = set()

    for access in admin_accesses:
        if access.role.vcode == 'SA':
            is_global = True
            break
        elif access.role.vcode == 'ADM':
            if access.nid_department:
                allowed_dept_ids.add(access.nid_department)
        elif access.role.vcode == 'PIC':
            if access.nid_lab:
                allowed_lab_ids.add(access.nid_lab)

    # If Admin, get labs from departments
    if not is_global and allowed_dept_ids:
        dept_labs = db.query(departmentLabModel.DepartmentLab.nid_lab).filter(
            departmentLabModel.DepartmentLab.nid_department.in_(allowed_dept_ids),
            departmentLabModel.DepartmentLab.nstatus == 1
        ).all()
        for dl in dept_labs:
            allowed_lab_ids.add(dl.nid_lab)

    return is_global, allowed_lab_ids


def check_lab_access(db: Session, current_user: usersSchema.User, lab_id: int) -> bool:
    """Check if user has access to specific lab"""
    is_global, allowed_lab_ids = _get_user_scope_info(db, current_user)
    
    if is_global:
        return True
    
    return lab_id in allowed_lab_ids


# --- CRUD OPERATIONS ---

def get_articles(
    db: Session,
    current_user: usersSchema.User,
    skip: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    nid_lab: Optional[int] = None,
    nstatus: Optional[int] = None,
    nis_featured: Optional[int] = None,
):
    """Get articles with scoping"""
    # 1. Get scope
    is_global, allowed_lab_ids = _get_user_scope_info(db, current_user)
    
    # 2. Base query with joins for display names
    query = db.query(
        models.LabArticle,
        labModel.Lab.vname.label('lab_name'),
        usersModel.User.vname.label('author_name')
    ).join(
        labModel.Lab, models.LabArticle.nid_lab == labModel.Lab.nid
    ).join(
        usersModel.User, models.LabArticle.nid_user == usersModel.User.nid
    )
    
    # 3. Apply scope filter
    if not is_global:
        if not allowed_lab_ids:
            return {"data": [], "total": 0}
        query = query.filter(models.LabArticle.nid_lab.in_(allowed_lab_ids))
    
    # 4. Apply filters
    if nid_lab:
        query = query.filter(models.LabArticle.nid_lab == nid_lab)
    if nstatus is not None:
        query = query.filter(models.LabArticle.nstatus == nstatus)
    if nis_featured is not None:
        query = query.filter(models.LabArticle.nis_featured == nis_featured)
    if search:
        search_filter = or_(
            models.LabArticle.vtitle.ilike(f"%{search}%"),
            models.LabArticle.vexcerpt.ilike(f"%{search}%"),
        )
        query = query.filter(search_filter)
    
    # 5. Pagination
    total = query.count()
    query = query.order_by(models.LabArticle.dsort_at.desc())
    results = query.offset(skip).limit(limit).all()
    
    # 6. Format response
    data = []
    for article, lab_name, author_name in results:
        article_dict = article.__dict__.copy()
        article_dict['lab_name'] = lab_name
        article_dict['author_name'] = author_name
        article_dict['tags'] = article.tags  # Eager load tags
        data.append(article_dict)
    
    return {"data": data, "total": total}


def get_article_by_code(db: Session, vcode: str):
    """Get single article by code"""
    return db.query(models.LabArticle).filter(
        models.LabArticle.vcode == vcode
    ).first()


def get_article_by_code_public(db: Session, vcode: str):
    """Get article for public display with lab info"""
    result = db.query(
        models.LabArticle,
        labModel.Lab.vname.label('lab_name'),
        labModel.Lab.vcode.label('lab_code'),
        usersModel.User.vname.label('author_name')
    ).join(
        labModel.Lab, models.LabArticle.nid_lab == labModel.Lab.nid
    ).join(
        usersModel.User, models.LabArticle.nid_user == usersModel.User.nid
    ).filter(
        models.LabArticle.vcode == vcode,
        models.LabArticle.nstatus == 1
    ).first()
    
    if not result:
        return None
    
    article, lab_name, lab_code, author_name = result
    return {
        "article": article,
        "lab_name": lab_name,
        "lab_code": lab_code,
        "author_name": author_name,
        "tags": [tag.vtag for tag in article.tags]
    }


def get_public_articles(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    lab_code: Optional[str] = None,
    search: Optional[str] = None,
):
    """Get articles for public display (active only)"""
    query = db.query(
        models.LabArticle,
        labModel.Lab.vname.label('lab_name'),
        labModel.Lab.vcode.label('lab_code'),
        usersModel.User.vname.label('author_name')
    ).join(
        labModel.Lab, models.LabArticle.nid_lab == labModel.Lab.nid
    ).join(
        usersModel.User, models.LabArticle.nid_user == usersModel.User.nid
    ).filter(
        models.LabArticle.nstatus == 1
    )
    
    if lab_code:
        query = query.filter(labModel.Lab.vcode == lab_code)
    
    if search:
        search_filter = or_(
            models.LabArticle.vtitle.ilike(f"%{search}%"),
            models.LabArticle.vexcerpt.ilike(f"%{search}%"),
        )
        query = query.filter(search_filter)
    
    total = query.count()
    query = query.order_by(models.LabArticle.dpublished_at.desc().nullslast())
    results = query.offset(skip).limit(limit).all()
    
    data = []
    for article, lab_name, lab_code, author_name in results:
        data.append({
            "vcode": article.vcode,
            "vtitle": article.vtitle,
            "vexcerpt": article.vexcerpt,
            "vthumbnail": article.vthumbnail,
            "dpublished_at": article.dpublished_at,
            "lab_name": lab_name,
            "lab_code": lab_code,
            "author_name": author_name,
            "tags": [tag.vtag for tag in article.tags],
            "nis_featured": article.nis_featured
        })
    
    return {"data": data, "total": total}


def create_article(
    db: Session,
    article: schema.LabArticleCreate,
    current_user: usersSchema.User
):
    """Create new article"""
    # Check lab access
    if not check_lab_access(db, current_user, article.nid_lab):
        raise ValueError("You don't have access to create articles for this lab")
    
    # Determine status based on schedule
    # If dpublished_at is None or empty or in the past -> publish immediately (nstatus=1)
    # If dpublished_at is in the future -> schedule (nstatus=2)
    now = now_wib()
    
    if article.dpublished_at and article.dpublished_at > now:
        # Future date = scheduled
        article_status = 2
        publish_date = article.dpublished_at
    else:
        # Empty or past date = publish immediately
        article_status = 1
        publish_date = now if not article.dpublished_at else article.dpublished_at
    
    # Create article
    db_article = models.LabArticle(
        vcode=generate_article_code(),
        nid_lab=article.nid_lab,
        nid_user=current_user.nid,
        vtitle=article.vtitle,
        vexcerpt=article.vexcerpt,
        vcontent=article.vcontent,
        vthumbnail=article.vthumbnail,
        nis_featured=article.nis_featured or 0,
        dpublished_at=publish_date,
        vcreated_by=current_user.vcode,
        nstatus=article_status
    )
    
    # Enforce Singleton Featured Logic
    if article.nis_featured == 1:
        db.query(models.LabArticle).filter(
            models.LabArticle.nstatus == 1,
            models.LabArticle.nis_featured == 1
        ).update({models.LabArticle.nis_featured: 0}, synchronize_session=False)
    
    db.add(db_article)
    db.flush()  # Get nid for tags
    
    # Add tags
    if article.tags:
        for tag_name in article.tags[:5]:  # Ensure max 5
            db_tag = models.ArticleTag(
                nid_article=db_article.nid,
                vtag=tag_name
            )
            db.add(db_tag)
    
    db.commit()
    db.refresh(db_article)
    
    return db_article


def update_article(
    db: Session,
    vcode: str,
    article: schema.LabArticleUpdate,
    current_user: usersSchema.User
):
    """Update existing article"""
    db_article = get_article_by_code(db, vcode)
    if not db_article:
        raise ValueError("Article not found")
    
    # Check lab access
    if not check_lab_access(db, current_user, db_article.nid_lab):
        raise ValueError("You don't have access to update this article")
    
    # Update fields
    update_data = article.model_dump(exclude_unset=True)
    tags_data = update_data.pop('tags', None)
    
    # Enforce Singleton Featured Logic if being set to 1
    if update_data.get('nis_featured') == 1:
        db.query(models.LabArticle).filter(
            models.LabArticle.nstatus == 1,
            models.LabArticle.nis_featured == 1,
            models.LabArticle.nid != db_article.nid
        ).update({models.LabArticle.nis_featured: 0}, synchronize_session=False)
    
    for field, value in update_data.items():
        if value is not None:
            setattr(db_article, field, value)
    
    db_article.vmodified_by = current_user.vcode
    db_article.dmodified_at = now_wib()
    db_article.dsort_at = now_wib()
    
    # Update tags if provided
    if tags_data is not None:
        # Delete existing tags
        db.query(models.ArticleTag).filter(
            models.ArticleTag.nid_article == db_article.nid
        ).delete()
        
        # Add new tags
        for tag_name in tags_data[:5]:
            db_tag = models.ArticleTag(
                nid_article=db_article.nid,
                vtag=tag_name
            )
            db.add(db_tag)
    
    db.commit()
    db.refresh(db_article)
    
    return db_article


def delete_article(db: Session, vcode: str, current_user: usersSchema.User):
    """Soft delete article (set nstatus=0)"""
    db_article = get_article_by_code(db, vcode)
    if not db_article:
        raise ValueError("Article not found")
    
    # Check lab access
    if not check_lab_access(db, current_user, db_article.nid_lab):
        raise ValueError("You don't have access to delete this article")
    
    db_article.nstatus = 0
    db_article.vmodified_by = current_user.vcode
    db_article.dmodified_at = now_wib()
    
    db.commit()
    
    return db_article


# --- SCOPED DROPDOWN ---

def get_scoped_labs_for_article(db: Session, current_user: usersSchema.User):
    """Get labs user can create/edit articles for"""
    is_global, allowed_lab_ids = _get_user_scope_info(db, current_user)
    
    query = db.query(labModel.Lab).filter(labModel.Lab.nstatus == 1)
    
    if not is_global:
        if not allowed_lab_ids:
            return {"data": []}
        query = query.filter(labModel.Lab.nid.in_(allowed_lab_ids))
    
    query = query.order_by(labModel.Lab.vname.asc())
    data = query.all()
    
    return {"data": data}


# --- SCHEDULED PUBLISHING ---

def publish_scheduled_articles(db: Session):
    """
    Cron job function to publish scheduled articles.
    Articles with nstatus=2 (scheduled) and dpublished_at <= now will be set to nstatus=1 (published).
    """
    now = now_wib()
    
    # Find articles that are scheduled (nstatus=2) and their publish time has passed
    scheduled_articles = db.query(models.LabArticle).filter(
        models.LabArticle.nstatus == 2,  # Scheduled status
        models.LabArticle.dpublished_at != None,
        models.LabArticle.dpublished_at <= now
    ).all()
    
    updated_count = 0
    for article in scheduled_articles:
        article.nstatus = 1  # Set to published
        article.dmodified_at = now
        article.vmodified_by = "SYSTEM_CRON"
        updated_count += 1
    
    if updated_count > 0:
        db.commit()
    
    return {"updated_count": updated_count, "articles": [a.vcode for a in scheduled_articles]}
