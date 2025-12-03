from sqlalchemy import or_, UniqueConstraint, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from fastapi import UploadFile, Request, HTTPException
from typing import List, Optional, Set
from ..models import labModel as models
from ..models import departmentLabModel, userAccessModel, rolesModel, labGalleryModel, filesModel
from ..schemas import labSchema as schema, usersSchema
from ..controller import fileController

import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")
def now_wib():
    return datetime.now(JAKARTA_TZ)

# --- HELPERS ---

def to_wib(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        return JAKARTA_TZ.localize(dt)
    return dt.astimezone(JAKARTA_TZ)


def _process_lab_images(db: Session, lab_id: int, hero_vcode: str | None, gallery_vcodes: list[str] | None, current_user: usersSchema.User):
    # 1. Handle Hero Image (ntype=1)
    if hero_vcode:
        # Check if file exists
        hero_file = db.query(filesModel.Files).filter(filesModel.Files.vcode == hero_vcode).first()
        if hero_file:
            # Deactivate existing hero
            existing_hero = db.query(labGalleryModel.LabGallery).filter(
                labGalleryModel.LabGallery.nid_lab == lab_id,
                labGalleryModel.LabGallery.ntype == 1,
                labGalleryModel.LabGallery.nstatus == 1
            ).first()
            
            if existing_hero and existing_hero.file.vcode != hero_vcode:
                 existing_hero.nstatus = 0
                 existing_hero.vmodified_by = current_user.vcode
                 existing_hero.dmodified_at = now_wib()

            if not existing_hero or existing_hero.file.vcode != hero_vcode:
                # Create new hero entry
                new_hero = labGalleryModel.LabGallery(
                    vcode=f"LG-{lab_id}-HERO-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    nid_lab=lab_id,
                    nid_file=hero_file.nid,
                    ntype=1,
                    nstatus=1,
                    vcreated_by=current_user.vcode
                )
                db.add(new_hero)

    # 2. Handle Gallery Images (ntype=2)
    if gallery_vcodes is not None:
        # Get current active gallery items
        current_gallery = db.query(labGalleryModel.LabGallery).join(filesModel.Files).filter(
            labGalleryModel.LabGallery.nid_lab == lab_id,
            labGalleryModel.LabGallery.ntype == 2,
            labGalleryModel.LabGallery.nstatus == 1
        ).all()
        
        current_vcodes = {item.file.vcode: item for item in current_gallery}
        input_vcodes = set(gallery_vcodes)
        
        # A. Soft Delete (Present in Current but NOT in Input)
        for vcode, item in current_vcodes.items():
            if vcode not in input_vcodes:
                item.nstatus = 0
                item.vmodified_by = current_user.vcode
                item.dmodified_at = now_wib()
        
        # B. Insert New (Present in Input but NOT in Current)
        for vcode in input_vcodes:
            if vcode not in current_vcodes:
                file_obj = db.query(filesModel.Files).filter(filesModel.Files.vcode == vcode).first()
                if file_obj:
                    new_gallery = labGalleryModel.LabGallery(
                        vcode=f"LG-{lab_id}-GAL-{file_obj.nid}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        nid_lab=lab_id,
                        nid_file=file_obj.nid,
                        ntype=2,
                        nstatus=1,
                        vcreated_by=current_user.vcode
                    )
                    db.add(new_gallery)


def get_lab_by_code_and_name(db: Session, vcode: str, vname: str):
    return db.query(models.Lab).filter(
        and_(
            models.Lab.vcode == vcode,
            models.Lab.vname == vname
        )
    ).first()


def get_lab_by_code(db: Session, lab_code: str):
    return db.query(models.Lab).filter(models.Lab.vcode == lab_code).first()


def get_lab(db: Session, lab_id: int):
    return db.query(models.Lab).filter(models.Lab.nid == lab_id).first()


# --- NEW: File Handling Functions (Booking Pattern) ---

async def create_lab_with_files(
    db: Session,
    lab: schema.LabCreate,
    current_user: usersSchema.User,
    request: Request,
    hero_image: Optional[UploadFile],
    gallery_images: Optional[List[UploadFile]]
):
    """
    Create lab with file uploads. Follows bookingController pattern.
    """
    print(f"[LabController] Creating lab: {lab.vcode}")
    
    # Track files for rollback
    uploaded_file_ids: List[int] = []
    processed_filenames: Set[str] = set()
    
    try:
        # 1. Save Hero Image
        hero_vcode = None
        if hero_image and hero_image.filename:
            print(f"[LabController] Processing Hero: {hero_image.filename}")
            db_hero_file = await fileController.save_file(
                db=db,
                file=hero_image,
                category="labs/hero",
                current_user=current_user,
                request=request,
                is_public=True
            )
            hero_vcode = db_hero_file.vcode
            uploaded_file_ids.append(db_hero_file.nid)
            processed_filenames.add(hero_image.filename)
            print(f"[LabController] Hero saved: {hero_vcode}")
        
        # 2. Save Gallery Images (with deduplication)
        gallery_vcodes = []
        if gallery_images:
            print(f"[LabController] Processing {len(gallery_images)} gallery candidates...")
            for img in gallery_images:
                # Skip empty or duplicate filenames
                if not img.filename or img.filename in processed_filenames:
                    print(f" - [Skip] Duplicate/Empty: {img.filename}")
                    continue
                
                print(f" - [Saving] {img.filename}")
                db_gallery_file = await fileController.save_file(
                    db=db,
                    file=img,
                    category="labs/gallery",
                    current_user=current_user,
                    request=request,
                    is_public=True
                )
                gallery_vcodes.append(db_gallery_file.vcode)
                uploaded_file_ids.append(db_gallery_file.nid)
                processed_filenames.add(img.filename)
                print(f" - [Saved] {img.filename} -> {db_gallery_file.vcode}")
        
        # 3. Flush files to DB (but don't commit yet)
        db.flush()
        
        # 4. Create Lab Record
        lab_data = lab.model_dump(exclude={'hero_image_vcode', 'gallery_image_vcodes'})
        db_lab = models.Lab(**lab_data)
        db_lab.vcreated_by = current_user.vcode
        db_lab.dsort_at = now_wib()
        
        db.add(db_lab)
        db.commit()
        db.refresh(db_lab)
        
        # 5. Link Files to Lab
        _process_lab_images(db, db_lab.nid, hero_vcode, gallery_vcodes, current_user)
        db.commit()
        
        print(f"[LabController] Lab created successfully: {db_lab.vcode}")
        return db_lab
        
    except IntegrityError as e:
        db.rollback()
        # Cleanup uploaded files
        for file_id in uploaded_file_ids:
            try:
                fileController.permanently_delete_file_record(db, file_id)
            except Exception:
                pass
        
        error_info = str(e.orig).lower()
        print("IntegrityError:", error_info)
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
            if 'vcode' in error_info and 'vname' not in error_info:
                raise ValueError("Failed to save. The provided Code is already in use.")
            else:
                raise ValueError("Failed to save. The provided Code and Name combination is already in use.")
        else:
            raise ValueError("The operation could not be completed. Please review your data or refresh the page and try again.")
    
    except Exception as e:
        db.rollback()
        # Cleanup uploaded files
        for file_id in uploaded_file_ids:
            try:
                fileController.permanently_delete_file_record(db, file_id)
            except Exception:
                pass
        print(f"[LabController] Error creating lab: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create lab: {str(e)}")


async def update_lab_with_files(
    db: Session,
    lab_vcode: str,
    lab: schema.LabUpdate,
    current_user: usersSchema.User,
    request: Request,
    hero_image: Optional[UploadFile],
    gallery_images: Optional[List[UploadFile]],
    existing_gallery_vcodes: Optional[List[str]]
):
    """
    Update lab with file uploads. Follows bookingController pattern.
    """
    print(f"[LabController] Updating lab: {lab_vcode}")
    
    db_lab = get_lab_by_code(db, lab_code=lab_vcode)
    if not db_lab:
        raise HTTPException(status_code=404, detail="Lab not found")
    
    # Track files for rollback
    uploaded_file_ids: List[int] = []
    processed_filenames: Set[str] = set()
    
    try:
        # 1. Save New Hero Image (if provided)
        hero_vcode = None
        if hero_image and hero_image.filename:
            print(f"[LabController] Processing New Hero: {hero_image.filename}")
            db_hero_file = await fileController.save_file(
                db=db,
                file=hero_image,
                category="labs/hero",
                current_user=current_user,
                request=request,
                is_public=True
            )
            hero_vcode = db_hero_file.vcode
            uploaded_file_ids.append(db_hero_file.nid)
            processed_filenames.add(hero_image.filename)
            print(f"[LabController] New Hero saved: {hero_vcode}")
        
        # 2. Save New Gallery Images (with deduplication)
        new_gallery_vcodes = []
        if gallery_images:
            print(f"[LabController] Processing {len(gallery_images)} new gallery candidates...")
            for img in gallery_images:
                if not img.filename or img.filename in processed_filenames:
                    print(f" - [Skip] Duplicate/Empty: {img.filename}")
                    continue
                
                print(f" - [Saving] {img.filename}")
                db_gallery_file = await fileController.save_file(
                    db=db,
                    file=img,
                    category="labs/gallery",
                    current_user=current_user,
                    request=request,
                    is_public=True
                )
                new_gallery_vcodes.append(db_gallery_file.vcode)
                uploaded_file_ids.append(db_gallery_file.nid)
                processed_filenames.add(img.filename)
                print(f" - [Saved] {img.filename} -> {db_gallery_file.vcode}")
        
        # 3. Combine existing + new gallery vcodes
        final_gallery_vcodes = []
        if existing_gallery_vcodes:
            final_gallery_vcodes.extend(existing_gallery_vcodes)
        final_gallery_vcodes.extend(new_gallery_vcodes)
        
        # 4. Flush files to DB
        db.flush()
        
        # 5. Update Lab Record
        db_lab.vcode = lab.vcode
        db_lab.vname = lab.vname
        db_lab.vdesc = lab.vdesc
        db_lab.nid_building = lab.nid_building
        db_lab.vroom_number = lab.vroom_number
        db_lab.ncapacity = lab.ncapacity
        db_lab.nstatus = lab.nstatus
        db_lab.vmodified_by = current_user.vcode
        db_lab.dsort_at = now_wib()
        
        db.commit()
        db.refresh(db_lab)
        
        # 6. Update File Links
        _process_lab_images(db, db_lab.nid, hero_vcode, final_gallery_vcodes, current_user)
        db.commit()
        
        print(f"[LabController] Lab updated successfully: {db_lab.vcode}") 
        return db_lab
        
    except IntegrityError as e:
        db.rollback()
        # Cleanup uploaded files
        for file_id in uploaded_file_ids:
            try:
                fileController.permanently_delete_file_record(db, file_id)
            except Exception:
                pass
        
        error_info = str(e.orig).lower()
        print("IntegrityError:", error_info)
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
            if 'vcode' in error_info and 'vname' not in error_info:
                raise ValueError("Failed to update. The provided Code is already in use.")
            else:
                raise ValueError("Failed to update. The provided Code and Name combination is already in use.")
        else:
            raise ValueError("The operation could not be completed. Please review your data or refresh the page and try again.")
    
    except Exception as e:
        db.rollback()
        # Cleanup uploaded files
        for file_id in uploaded_file_ids:
            try:
                fileController.permanently_delete_file_record(db, file_id)
            except Exception:
                pass
        print(f"[LabController] Error updating lab: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update lab: {str(e)}")


# --- OLD: Simple Create/Update (for backward compatibility) ---

def create_lab(db: Session, lab: schema.LabCreate, current_user: usersSchema.User):
    lab_data_dict = lab.model_dump(exclude={'hero_image_vcode', 'gallery_image_vcodes'})
    db_lab = models.Lab(**lab_data_dict)
    db_lab.vcreated_by = current_user.vcode
    db_lab.dsort_at = now_wib()

    try:
        db.add(db_lab)
        db.commit()
        db.refresh(db_lab)
        
        _process_lab_images(db, db_lab.nid, lab.hero_image_vcode, lab.gallery_image_vcodes, current_user)
        db.commit()

        return db_lab
    except IntegrityError as e:
        db.rollback()
        error_info = str(e.orig).lower()
        print("IntegrityError:", error_info)
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
            if 'vcode' in error_info and 'vname' not in error_info:
                 raise ValueError("Failed to save. The provided Code is already in use.")
            else:
                 raise ValueError("Failed to save. The provided Code and Name combination is already in use.")
        else:
            raise ValueError("The operation could not be completed. Please review your data or refresh the page and try again.")


def update_lab(db: Session, lab_vcode: str, lab: schema.LabUpdate, current_user: usersSchema.User):
    db_lab = get_lab_by_code(db, lab_code=lab_vcode)
    if not db_lab:
        return None

    db_lab.vcode = lab.vcode
    db_lab.vname = lab.vname
    db_lab.vdesc = lab.vdesc
    db_lab.nid_building = lab.nid_building
    db_lab.vroom_number = lab.vroom_number
    db_lab.ncapacity = lab.ncapacity
    db_lab.nstatus = lab.nstatus
    db_lab.vmodified_by = current_user.vcode
    db_lab.dsort_at = now_wib()

    try:
        db.commit()
        db.refresh(db_lab)
        
        _process_lab_images(db, db_lab.nid, lab.hero_image_vcode, lab.gallery_image_vcodes, current_user)
        db.commit()

        return db_lab
    except IntegrityError as e:
        db.rollback()
        error_info = str(e.orig).lower()
        print("IntegrityError:", error_info)
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
            if 'vcode' in error_info and 'vname' not in error_info:
                 raise ValueError("Failed to update. The provided Code is already in use.")
            else:
                 raise ValueError("Failed to update. The provided Code and Name combination is already in use.")
        else:
            raise ValueError("The operation could not be completed. Please review your data or refresh the page and try again.")

def get_labs(
    db: Session,
    current_user: usersSchema.User, 
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    vname: str | None = None,
    vcode: str | None = None,
    vdesc: str | None = None,
    nstatus: int | None = None,
):
    # 1. LOGIC SCOPE: Cek user ini SA atau Admin Dept mana
    admin_accesses = db.query(userAccessModel.UserAccess).join(
        rolesModel.Role, userAccessModel.UserAccess.nid_role == rolesModel.Role.nid
    ).filter(
        userAccessModel.UserAccess.nid_user == current_user.nid,
        userAccessModel.UserAccess.nstatus == 1
    ).all()

    is_global = False
    allowed_dept_ids = set()

    for access in admin_accesses:
        if access.role.vcode == 'SA':
            is_global = True
            break
        elif access.role.vcode == 'ADM':
            if access.nid_department:
                allowed_dept_ids.add(access.nid_department)

    # 2. Build Base Query
    query = db.query(models.Lab)

    # 3. Apply Scope Filter (Jika bukan SA)
    if not is_global:
        if not allowed_dept_ids:
            # Admin tanpa departemen -> return kosong
            return {"data": [], "total": 0}
        
        # Join ke DepartmentLab untuk memfilter lab yang dimiliki departemen admin
        query = query.join(
            departmentLabModel.DepartmentLab,
            models.Lab.nid == departmentLabModel.DepartmentLab.nid_lab
        ).filter(
            departmentLabModel.DepartmentLab.nid_department.in_(allowed_dept_ids),
            departmentLabModel.DepartmentLab.nstatus == 1
        ).distinct() # Hindari duplikat jika lab terhubung ke multiple dept milik admin yg sama

    # 4. Filter Pencarian Standar (Existing Logic)
    if search:
        search_filter = or_(
            models.Lab.vname.ilike(f"%{search}%"),
            models.Lab.vcode.ilike(f"%{search}%"),
            models.Lab.vdesc.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    if vname:
        query = query.filter(models.Lab.vname.ilike(f"%{vname}%"))
    if vcode:
        query = query.filter(models.Lab.vcode.ilike(f"%{vcode}%"))
    if vdesc:
        query = query.filter(models.Lab.vdesc.ilike(f"%{vdesc}%"))
    if nstatus is not None:
        query = query.filter(models.Lab.nstatus == nstatus)

    # 5. Pagination & Return
    total = query.count()
    query = query.order_by(models.Lab.dsort_at.desc())
    data = query.offset(skip).limit(limit).all()

    return {"data": data, "total": total}


def delete_lab(db: Session, lab_vcode: str, current_user: usersSchema.User):
    db_lab = db.query(models.Lab).filter(models.Lab.vcode == lab_vcode).first()
    if db_lab:
        db_lab.nstatus = 0
        db_lab.vmodified_by = current_user.vcode
        db_lab.dsort_at = now_wib()
        db.commit()
        db.refresh(db_lab)
    return db_lab


def get_all_active_labs_for_dropdown(db: Session):
    labs = (
        db.query(models.Lab)
        .order_by(models.Lab.vname)
        .all()
    )
    return {"data": labs}

def get_all_labs_for_dropdown(db: Session):
    labs = (
        db.query(models.Lab)
        .filter(models.Lab.nstatus == 1)
        .order_by(models.Lab.vname)
        .all()
    )
    return {"data": labs}

def get_scoped_labs_for_dropdown(db: Session, current_user: usersSchema.User):
    """
    [SCOPED] Mengambil SEMUA lab (Active/Inactive) berdasarkan departemen Admin.
    """
    return _get_labs_by_scope_logic(db, current_user, only_active=False)

def get_scoped_active_labs_for_dropdown(db: Session, current_user: usersSchema.User):
    """
    [SCOPED] Mengambil lab AKTIF saja berdasarkan departemen Admin.
    """
    return _get_labs_by_scope_logic(db, current_user, only_active=True)


# --- Helper Internal untuk Logic Scope ---
def _get_labs_by_scope_logic(db: Session, current_user: usersSchema.User, only_active: bool):
    # 1. Cek Scope User
    admin_accesses = db.query(userAccessModel.UserAccess).join(
        rolesModel.Role, userAccessModel.UserAccess.nid_role == rolesModel.Role.nid
    ).filter(
        userAccessModel.UserAccess.nid_user == current_user.nid,
        userAccessModel.UserAccess.nstatus == 1
    ).all()

    is_global = False
    allowed_dept_ids = set()

    for access in admin_accesses:
        if access.role.vcode == 'SA':
            is_global = True
            break
        elif access.role.vcode == 'ADM':
            if access.nid_department:
                allowed_dept_ids.add(access.nid_department)

    # 2. Build Base Query
    query = db.query(models.Lab)
    if only_active:
        query = query.filter(models.Lab.nstatus == 1)

    # 3. Apply Filter Scope
    if not is_global:
        if not allowed_dept_ids:
            return {"data": []}
            
        query = query.join(
            departmentLabModel.DepartmentLab, 
            models.Lab.nid == departmentLabModel.DepartmentLab.nid_lab
        ).filter(
            departmentLabModel.DepartmentLab.nid_department.in_(allowed_dept_ids),
            departmentLabModel.DepartmentLab.nstatus == 1
        ).distinct()

    # 4. Return
    query = query.order_by(models.Lab.vname.asc())
    data = query.all()
    return {"data": data}