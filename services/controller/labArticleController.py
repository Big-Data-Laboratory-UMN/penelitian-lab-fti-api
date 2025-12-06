# services/controller/labArticleController.py

from sqlalchemy.orm import Session
from sqlalchemy import or_, case
from typing import Optional, List, Set
import re
from datetime import datetime
import pytz

from ..models import labArticleModel as models
from ..models import userAccessModel, rolesModel, departmentLabModel, labModel, usersModel
from ..schemas import labArticleSchema as schema
from ..schemas import usersSchema

WIB = pytz.timezone("Asia/Jakarta")

def now_wib():
    return datetime.now(WIB)


def to_wib(dt: datetime) -> datetime:
    """
    Convert naive datetime to WIB timezone.
    If datetime is naive (no timezone), treat it as WIB (what user selected).
    If datetime has timezone, convert to WIB.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Naive datetime - assume it's already in WIB (user's local time)
        return WIB.localize(dt)
    else:
        # Has timezone info - convert to WIB
        return dt.astimezone(WIB)


def generate_slug_from_title(title: str) -> str:
    """
    Convert title to URL-friendly slug.
    Example: "Hello World! @2024" -> "hello-world-2024"
    """
    # Convert to lowercase
    slug = title.lower()
    # Replace spaces and special chars with dashes
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    # Remove leading/trailing dashes
    slug = slug.strip('-')
    # Collapse multiple dashes into one
    slug = re.sub(r'-+', '-', slug)
    # Limit length to 100 chars
    slug = slug[:100]
    return slug


def get_unique_slug(db: Session, title: str, exclude_nid: int = None) -> str:
    """
    Generate unique slug from title. If duplicate exists, append -1, -2, etc.
    exclude_nid: Exclude this article ID when checking for duplicates (for update)
    """
    base_slug = generate_slug_from_title(title)
    
    if not base_slug:
        base_slug = "article"
    
    # Check if base slug exists
    query = db.query(models.LabArticle).filter(
        models.LabArticle.vcode == base_slug
    )
    if exclude_nid:
        query = query.filter(models.LabArticle.nid != exclude_nid)
    
    if not query.first():
        return base_slug
    
    # Find highest existing suffix
    # Look for slugs like: base_slug, base_slug-1, base_slug-2, etc.
    pattern = f"{base_slug}-%"
    existing = db.query(models.LabArticle.vcode).filter(
        models.LabArticle.vcode.like(pattern)
    )
    if exclude_nid:
        existing = existing.filter(models.LabArticle.nid != exclude_nid)
    existing = existing.all()
    
    max_suffix = 0
    for (vcode,) in existing:
        # Extract the suffix number
        suffix_part = vcode[len(base_slug)+1:]
        if suffix_part.isdigit():
            max_suffix = max(max_suffix, int(suffix_part))
    
    return f"{base_slug}-{max_suffix + 1}"


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
    # MySQL-compatible: Use CASE to sort NULLs last (nullslast() is PostgreSQL-only)
    query = query.order_by(
        case((models.LabArticle.dpublished_at.is_(None), 1), else_=0),
        models.LabArticle.dpublished_at.desc()
    )
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


def get_related_articles(db: Session, vcode: str, limit: int = 3):
    """
    Get related articles based on:
    1. Priority: Articles with matching tags
    2. Fallback: Articles from the same lab
    Excludes the current article.
    """
    # Get the current article
    current = db.query(models.LabArticle).filter(
        models.LabArticle.vcode == vcode,
        models.LabArticle.nstatus == 1
    ).first()
    
    if not current:
        return {"data": []}
    
    # Get current article's tags
    current_tags = [tag.vtag for tag in current.tags]
    
    related_vcodes = set()
    related_articles = []
    
    # Step 1: Find articles with matching tags (if article has tags)
    if current_tags:
        # Get article IDs that share at least one tag
        matching_article_ids = db.query(models.ArticleTag.nid_article).filter(
            models.ArticleTag.vtag.in_(current_tags),
            models.ArticleTag.nid_article != current.nid
        ).distinct().all()
        
        matching_ids = [aid for (aid,) in matching_article_ids]
        
        if matching_ids:
            tag_related = db.query(
                models.LabArticle,
                labModel.Lab.vname.label('lab_name'),
                usersModel.User.vname.label('author_name')
            ).join(
                labModel.Lab, models.LabArticle.nid_lab == labModel.Lab.nid
            ).join(
                usersModel.User, models.LabArticle.nid_user == usersModel.User.nid
            ).filter(
                models.LabArticle.nid.in_(matching_ids),
                models.LabArticle.nstatus == 1
            ).order_by(
                models.LabArticle.dpublished_at.desc()
            ).limit(limit).all()
            
            for article, lab_name, author_name in tag_related:
                if article.vcode not in related_vcodes:
                    related_vcodes.add(article.vcode)
                    related_articles.append({
                        "vcode": article.vcode,
                        "vtitle": article.vtitle,
                        "vthumbnail": article.vthumbnail,
                        "lab_name": lab_name,
                        "author_name": author_name,
                    })
    
    # Step 2: If not enough, fill with articles from the same lab
    if len(related_articles) < limit:
        remaining = limit - len(related_articles)
        exclude_vcodes = list(related_vcodes) + [vcode]
        
        lab_related = db.query(
            models.LabArticle,
            labModel.Lab.vname.label('lab_name'),
            usersModel.User.vname.label('author_name')
        ).join(
            labModel.Lab, models.LabArticle.nid_lab == labModel.Lab.nid
        ).join(
            usersModel.User, models.LabArticle.nid_user == usersModel.User.nid
        ).filter(
            models.LabArticle.nid_lab == current.nid_lab,
            models.LabArticle.nstatus == 1,
            models.LabArticle.vcode.notin_(exclude_vcodes)
        ).order_by(
            models.LabArticle.dpublished_at.desc()
        ).limit(remaining).all()
        
        for article, lab_name, author_name in lab_related:
            related_articles.append({
                "vcode": article.vcode,
                "vtitle": article.vtitle,
                "vthumbnail": article.vthumbnail,
                "lab_name": lab_name,
                "author_name": author_name,
            })
    
    return {"data": related_articles}


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
    
    # Convert dpublished_at to WIB timezone, then strip timezone for MySQL storage
    scheduled_date = to_wib(article.dpublished_at).replace(tzinfo=None) if article.dpublished_at else None
    now_naive = now.replace(tzinfo=None)
    
    if scheduled_date and scheduled_date > now_naive:
        # Future date = scheduled
        article_status = 2
        publish_date = scheduled_date
    else:
        # Empty or past date = publish immediately
        article_status = 1
        publish_date = now_naive if not scheduled_date else scheduled_date
    
    # Create article with slug from title
    db_article = models.LabArticle(
        vcode=get_unique_slug(db, article.vtitle),
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
    
    # Check lab access (current lab)
    if not check_lab_access(db, current_user, db_article.nid_lab):
        raise ValueError("You don't have access to update this article")
    
    # Update fields
    update_data = article.model_dump(exclude_unset=True)
    tags_data = update_data.pop('tags', None)
    
    # If changing lab, check access to new lab
    new_lab_id = update_data.get('nid_lab')
    if new_lab_id and new_lab_id != db_article.nid_lab:
        if not check_lab_access(db, current_user, new_lab_id):
            raise ValueError("You don't have access to move article to this lab")
    
    # Enforce Singleton Featured Logic if being set to 1
    if update_data.get('nis_featured') == 1:
        db.query(models.LabArticle).filter(
            models.LabArticle.nstatus == 1,
            models.LabArticle.nis_featured == 1,
            models.LabArticle.nid != db_article.nid
        ).update({models.LabArticle.nis_featured: 0}, synchronize_session=False)
    
    # If title is being updated, regenerate the slug
    new_title = update_data.get('vtitle')
    if new_title and new_title != db_article.vtitle:
        new_slug = get_unique_slug(db, new_title, exclude_nid=db_article.nid)
        db_article.vcode = new_slug
    
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
    # Use naive datetime for comparison since MySQL stores naive datetime
    now = now_wib().replace(tzinfo=None)
    
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


def publish_single_article(article_vcode: str, db_factory):
    """
    Publish a single scheduled article by its vcode.
    Called by APScheduler at the exact scheduled time.
    """
    db = db_factory()
    try:
        print(f"\n[SCHEDULED PUBLISH] Publishing article: {article_vcode}")
        now = now_wib().replace(tzinfo=None)
        
        article = db.query(models.LabArticle).filter(
            models.LabArticle.vcode == article_vcode,
            models.LabArticle.nstatus == 2  # Must still be scheduled
        ).first()
        
        if article:
            article.nstatus = 1  # Set to published
            article.dmodified_at = now
            article.vmodified_by = "SYSTEM_SCHEDULED"
            db.commit()
            print(f"[SCHEDULED PUBLISH SUCCESS] Article '{article_vcode}' published at {now}")
            return True
        else:
            print(f"[SCHEDULED PUBLISH SKIP] Article '{article_vcode}' not found or already published")
            return False
            
    except Exception as e:
        print(f"[SCHEDULED PUBLISH FAILED] Error publishing article '{article_vcode}': {e}")
        db.rollback()
        return False
    finally:
        db.close()


def schedule_article_publish(scheduler, db_factory, article_vcode: str, publish_datetime):
    """
    Schedule an article to be published at a specific time using APScheduler date trigger.
    
    Args:
        scheduler: APScheduler instance from app.state.scheduler
        db_factory: Database session factory (SessionLocal)
        article_vcode: The article's unique code
        publish_datetime: The datetime to publish (naive datetime in WIB)
    """
    from datetime import datetime as dt
    import pytz
    
    WIB = pytz.timezone("Asia/Jakarta")
    
    # Ensure we have timezone-aware datetime for scheduler
    if publish_datetime.tzinfo is None:
        run_date = WIB.localize(publish_datetime)
    else:
        run_date = publish_datetime
    
    job_id = f"publish_article_{article_vcode}"
    
    try:
        # Remove existing job if any (in case of reschedule)
        try:
            scheduler.remove_job(job_id)
            print(f"[SCHEDULER] Removed existing job: {job_id}")
        except:
            pass  # Job didn't exist
        
        # Add job with 'date' trigger for precise timing
        scheduler.add_job(
            publish_single_article,
            'date',
            run_date=run_date,
            args=[article_vcode, db_factory],
            id=job_id,
            replace_existing=True,
            misfire_grace_time=300  # 5 minutes grace period
        )
        print(f"[SCHEDULER] ✅ Scheduled article '{article_vcode}' to publish at {run_date}")
        return True
        
    except Exception as e:
        print(f"[SCHEDULER] ❌ Failed to schedule article '{article_vcode}': {e}")
        return False


def cancel_scheduled_article(scheduler, article_vcode: str):
    """
    Cancel a scheduled article publish job.
    """
    job_id = f"publish_article_{article_vcode}"
    try:
        scheduler.remove_job(job_id)
        print(f"[SCHEDULER] Removed job: {job_id}")
        return True
    except Exception as e:
        print(f"[SCHEDULER] Job not found or error removing: {job_id}")
        return False

