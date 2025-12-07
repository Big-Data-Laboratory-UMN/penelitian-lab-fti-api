# services/controller/landingPageController.py

import uuid
import traceback
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import update

import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def now_wib():
    return datetime.now(JAKARTA_TZ)


# --- Import Model & Schema ---
from ..models import landingPageModel as models
from ..schemas import landingPageSchema as schema


# --- Initialization ---
def initialize_landing_page(db: Session, created_by: str = "SYSTEM"):
    """
    Initialize default landing page content and 3 slides if not exists.
    Called on first access or via startup.
    """
    # Check if content already exists
    existing = db.query(models.LandingPageContent).first()
    if existing:
        return existing
    
    try:
        # Create main content
        content = models.LandingPageContent(
            vcode=f"LP-{uuid.uuid4().hex[:8].upper()}",
            vabout_header="",
            vabout_subtext="",
            vcreated_by=created_by,
            dcreated_at=now_wib()
        )
        db.add(content)
        db.flush()  # Get the ID
        
        # Create 3 default slides (empty)
        default_slides = [
            {"norder": 1, "vheader": "", "vsubtext": ""},
            {"norder": 2, "vheader": "", "vsubtext": ""},
            {"norder": 3, "vheader": "", "vsubtext": ""},
        ]
        
        for slide_data in default_slides:
            slide = models.LandingPageSlide(
                vcode=f"SLIDE-{uuid.uuid4().hex[:8].upper()}",
                nid_landing_page=content.nid,
                norder=slide_data["norder"],
                vheader=slide_data["vheader"],
                vsubtext=slide_data["vsubtext"],
                nstatus=1,
                vcreated_by=created_by,
                dcreated_at=now_wib()
            )
            db.add(slide)
        
        db.commit()
        db.refresh(content)
        return content
    
    except Exception as e:
        db.rollback()
        print(f"Error initializing landing page: {e}")
        traceback.print_exc()
        raise ValueError(f"Failed to initialize landing page: {e}")


# --- CRUD Operations ---
def get_landing_page_content(db: Session):
    """Get the single landing page content record with slides."""
    content = db.query(models.LandingPageContent).first()
    if not content:
        # Auto-initialize if not exists
        content = initialize_landing_page(db)
    return content


def update_landing_page_content(db: Session, content_data: schema.LandingPageContentUpdate):
    """Update about section content."""
    content = get_landing_page_content(db)
    
    try:
        update_data = content_data.model_dump(exclude_unset=True)
        update_data['dmodified_at'] = now_wib()
        
        stmt = update(models.LandingPageContent).where(
            models.LandingPageContent.nid == content.nid
        ).values(**update_data)
        
        db.execute(stmt)
        db.commit()
        db.refresh(content)
        return content
    
    except Exception as e:
        db.rollback()
        print(f"Error updating landing page content: {e}")
        traceback.print_exc()
        raise ValueError(f"Failed to update content: {e}")


def get_all_slides(db: Session):
    """Get all 3 slides ordered by norder."""
    content = get_landing_page_content(db)  # Ensure data exists
    return db.query(models.LandingPageSlide).filter(
        models.LandingPageSlide.nid_landing_page == content.nid
    ).order_by(models.LandingPageSlide.norder).all()


def get_slide_by_id(db: Session, slide_id: int):
    """Get a single slide by ID."""
    return db.query(models.LandingPageSlide).filter(
        models.LandingPageSlide.nid == slide_id
    ).first()


def update_slide(db: Session, slide_id: int, slide_data: schema.LandingPageSlideUpdate):
    """Update a single slide."""
    slide = get_slide_by_id(db, slide_id)
    if not slide:
        return None
    
    try:
        update_data = slide_data.model_dump(exclude_unset=True)
        update_data['dmodified_at'] = now_wib()
        
        stmt = update(models.LandingPageSlide).where(
            models.LandingPageSlide.nid == slide_id
        ).values(**update_data)
        
        db.execute(stmt)
        db.commit()
        db.refresh(slide)
        return slide
    
    except Exception as e:
        db.rollback()
        print(f"Error updating slide: {e}")
        traceback.print_exc()
        raise ValueError(f"Failed to update slide: {e}")


def update_slide_without_file(db: Session, slide_id: int, slide_data: schema.LandingPageSlideUpdate):
    """Update a single slide WITHOUT updating the file reference (preserves existing image)."""
    slide = get_slide_by_id(db, slide_id)
    if not slide:
        return None
    
    try:
        # Exclude nid_file from update data to preserve existing image
        update_data = slide_data.model_dump(exclude_unset=True, exclude={'nid_file'})
        update_data['dmodified_at'] = now_wib()
        
        stmt = update(models.LandingPageSlide).where(
            models.LandingPageSlide.nid == slide_id
        ).values(**update_data)
        
        db.execute(stmt)
        db.commit()
        db.refresh(slide)
        return slide
    
    except Exception as e:
        db.rollback()
        print(f"Error updating slide: {e}")
        traceback.print_exc()
        raise ValueError(f"Failed to update slide: {e}")


def get_public_landing_page(db: Session, base_url: str):
    """Get landing page data for public display with image URLs."""
    content = get_landing_page_content(db)
    slides = get_all_slides(db)
    
    # Build public slides with image URLs
    public_slides = []
    for slide in slides:
        image_url = None
        if slide.nid_file:
            # Use the /files/{file_id}/raw endpoint to serve images
            image_url = f"{base_url}/files/{slide.nid_file}/raw"
        
        public_slides.append({
            "norder": slide.norder,
            "vheader": slide.vheader,
            "vsubtext": slide.vsubtext,
            "image_url": image_url
        })
    
    return {
        "vabout_header": content.vabout_header,
        "vabout_subtext": content.vabout_subtext,
        "slides": public_slides
    }
