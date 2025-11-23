from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional

from ..schemas import labGallerySchema as schema, usersSchema
from ..controller import labGalleryController, usersController, auditLogController, userAccessController
from ..database import SessionLocal
from utils import permissions

router = APIRouter(
    prefix="/lab-gallery",
    tags=["Lab Gallery"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/{lab_id}", response_model=List[schema.LabGallery])
def get_gallery_by_lab(lab_id: int, db: Session = Depends(get_db)):
    return labGalleryController.get_gallery_by_lab_id(db, lab_id)

@router.get("/", response_model=schema.LabGalleryResponse)
def get_all_gallery_items(
    skip: int = 0,
    limit: int = 100,
    status: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    accessible_labs = permissions.get_accessible_labs_for_user(db, current_user.nid)
    return labGalleryController.get_all_gallery_items(db, skip, limit, status, search, accessible_labs)

@router.post("/", response_model=schema.LabGallery, status_code=status.HTTP_201_CREATED)
def create_gallery_item(
    gallery: schema.LabGalleryCreate, 
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    try:
        # Check if user can edit gallery for this lab (SA/ADM only, not PIC)
        if not permissions.can_edit_lab_gallery(db, current_user.nid, gallery.nid_lab):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Anda tidak memiliki akses untuk membuat galeri pada lab ini (hanya SA/ADM)."
            )
        new_gallery = labGalleryController.create_gallery_item(db=db, gallery=gallery, current_user=current_user)
        
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="CREATE",
            target_model="LabGallery",
            target_identifier=new_gallery.vcode,
            jbefore=None,
            jafter=gallery.model_dump(),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        
        return new_gallery
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{gallery_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gallery_item(
    gallery_id: int, 
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    # Get gallery item first to check lab access
    existing_gallery = labGalleryController.get_gallery_by_id(db, gallery_id)
    if not existing_gallery:
        raise HTTPException(status_code=404, detail="Gallery item not found")
    
    if not permissions.can_edit_lab_gallery(db, current_user.nid, existing_gallery.nid_lab):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak memiliki akses untuk menghapus galeri pada lab ini (hanya SA/ADM)."
        )
    
    deleted_gallery = labGalleryController.delete_gallery_item(db=db, gallery_id=gallery_id, current_user=current_user)
    if not deleted_gallery:
        raise HTTPException(status_code=404, detail="Gallery item not found")
    
    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="DELETE",
        target_model="LabGallery",
        target_identifier=str(gallery_id),
        jbefore=None,
        jafter=None,
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    return
