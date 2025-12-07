# services/api/landingPageAPI.py

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional

from ..schemas import landingPageSchema as schema, usersSchema
from ..controller import landingPageController, usersController, userAccessController, fileController
from ..database import SessionLocal

router = APIRouter(
    prefix="/landing-page",
    tags=["Landing Page"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_superadmin_only(db: Session, current_user: usersSchema.User):
    """Only Superadmin can access landing page management"""
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if "SA" not in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hanya Superadmin yang bisa mengakses fitur ini."
        )


# --- ADMIN ENDPOINTS (Superadmin Only) ---

@router.get("/", response_model=schema.LandingPageResponse)
def get_landing_page_data(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Get all landing page data (content + slides) - Superadmin only"""
    check_superadmin_only(db, current_user)
    content = landingPageController.get_landing_page_content(db)
    return {"data": content, "message": "Success"}


@router.put("/content", response_model=schema.LandingPageResponse)
def update_about_section(
    content_data: schema.LandingPageContentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Update about section content - Superadmin only"""
    check_superadmin_only(db, current_user)
    
    content_data.vmodified_by = current_user.vcode
    content = landingPageController.update_landing_page_content(db, content_data)
    return {"data": content, "message": "About section updated successfully"}


@router.get("/slides", response_model=schema.LandingPageSlidesResponse)
def get_all_slides(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Get all 3 carousel slides - Superadmin only"""
    check_superadmin_only(db, current_user)
    slides = landingPageController.get_all_slides(db)
    return {"data": slides, "message": "Success"}


@router.put("/slides/{slide_id}", response_model=schema.LandingPageSlideSchema)
async def update_slide(
    slide_id: int,
    request: Request,
    vheader: Optional[str] = Form(None),
    vsubtext: Optional[str] = Form(None),
    nstatus: Optional[int] = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Update a single slide with optional image upload - Superadmin only"""
    check_superadmin_only(db, current_user)
    
    # Check if slide exists
    existing_slide = landingPageController.get_slide_by_id(db, slide_id)
    if not existing_slide:
        raise HTTPException(status_code=404, detail="Slide not found")
    
    # Handle file upload if provided
    nid_file = None
    has_new_file = False
    if file and file.filename:
        try:
            saved_file = await fileController.save_file(
                db=db,
                file=file,
                category="landing-page",
                current_user=current_user,
                request=request,
                is_public=True,
                prefix="SLIDE"
            )
            nid_file = saved_file.nid
            has_new_file = True
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")
    
    # Build update data - only include nid_file if a new file was uploaded
    slide_update = schema.LandingPageSlideUpdate(
        vheader=vheader,
        vsubtext=vsubtext,
        nstatus=nstatus,
        nid_file=nid_file if has_new_file else None,
        vmodified_by=current_user.vcode
    )
    
    # If no new file, exclude nid_file from update to preserve existing image
    if not has_new_file:
        # Remove nid_file from the update by setting it explicitly in controller
        updated_slide = landingPageController.update_slide_without_file(db, slide_id, slide_update)
    else:
        updated_slide = landingPageController.update_slide(db, slide_id, slide_update)
    
    return updated_slide


# --- PUBLIC ENDPOINTS (No Auth) ---

@router.get("/public", response_model=schema.LandingPagePublicResponse)
def get_public_landing_page(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get landing page data for public display (no auth required)"""
    base_url = str(request.base_url).rstrip('/')
    data = landingPageController.get_public_landing_page(db, base_url)
    return {"data": data, "message": "Success"}
