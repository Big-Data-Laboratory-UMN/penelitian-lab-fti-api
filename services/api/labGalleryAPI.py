from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional

from ..schemas import labGallerySchema as schema, usersSchema
from ..controller import labGalleryController, usersController, auditLogController
from ..database import SessionLocal

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

@router.post("/", response_model=schema.LabGallery, status_code=status.HTTP_201_CREATED)
def create_gallery_item(
    gallery: schema.LabGalleryCreate, 
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    try:
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
