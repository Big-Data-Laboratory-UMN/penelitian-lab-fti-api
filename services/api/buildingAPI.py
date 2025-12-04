from fastapi import APIRouter, Depends, HTTPException, status,Request, BackgroundTasks # type: ignore
from sqlalchemy.orm import Session
from typing import List, Optional

from ..schemas import buildingSchema as schema, usersSchema
from ..schemas.buildingSchema import Building
from ..controller import auditLogController
from ..controller import buildingController, usersController, userAccessController
from ..database import SessionLocal

from datetime import datetime
import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def to_wib(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return JAKARTA_TZ.localize(dt) if dt.tzinfo is None else dt.astimezone(JAKARTA_TZ)

router = APIRouter(
    prefix="/buildings",
    tags=["Buildings"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
def check_forbidden_roles(db: Session, current_user: usersSchema.User):
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if "PIC" in user_roles or "VSTR" in user_roles or "ADM" in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk operasi ini."
        )

def check_adm_sa_only(db: Session, current_user: usersSchema.User):
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if "PIC" in user_roles or "VSTR" in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk operasi ini."
        )

@router.get("/", response_model=schema.BuildingResponse)
def read_all_buildings(
    skip: int = 0, 
    limit: int = 10, 
    search: Optional[str] = None, 
    buildingName: Optional[str] = None,
    buildingCode: Optional[str] = None,
    buildingDesc: Optional[str] = None,
    status: Optional[int] = None,
    db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_forbidden_roles(db, current_user)
    buildings_data = buildingController.get_buildings(
        db=db, skip=skip, limit=limit, search=search,
        vname=buildingName, vcode=buildingCode, vdesc=buildingDesc, nstatus=status
    )
    return buildings_data

@router.get("/{building_id}", response_model=schema.Building)
def get_building_by_id(building_id: int, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Mengambil data building spesifik berdasarkan ID.
    """
    check_forbidden_roles(db, current_user)
    building = buildingController.get_building(db=db, building_id=building_id)
    if building is None:
        raise HTTPException(status_code=404, detail="Building not found")
    return building


@router.post("/", response_model=schema.Building, status_code=status.HTTP_201_CREATED)
def create_new_building(building: schema.BuildingCreate,request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Membuat building baru.
    """
    check_forbidden_roles(db, current_user)
    try:
        new_building = buildingController.create_building(db=db, building=building, current_user=current_user)
        
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="CREATE",
            target_model="Building",
            target_identifier=new_building.vcode,
            jbefore=None,
            jafter=building.model_dump(),
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        
        return new_building
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{building_vcode}", response_model=schema.Building)
def update_existing_building(building_vcode: str, request: Request,background_tasks: BackgroundTasks, building: schema.BuildingUpdate, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Mengupdate building berdasarkan VCODE.
    """
    check_forbidden_roles(db, current_user)
    db_building_before = buildingController.get_building_by_code(db, building_code=building_vcode) #
    if not db_building_before:
        raise HTTPException(status_code=404, detail="Building not found")
    jbefore = Building.model_validate(db_building_before).model_dump(mode='json')
    try:
        updated_building = buildingController.update_building(db=db, building_vcode=building_vcode, building=building, current_user=current_user)
        background_tasks.add_task(
            auditLogController.create_activity_log_task,
            nid_user=current_user.nid,
            action="UPDATE",
            target_model="Building",
            target_identifier=updated_building.vcode,
            jbefore=jbefore, # Data SEBELUM
            jafter=building.model_dump(), # Data BARU (dari request body)
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        return updated_building
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{building_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_building(building_vcode: str,request: Request,background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Melakukan soft delete pada building berdasarkan VCODE.
    """
    check_forbidden_roles(db, current_user)
    
    # --- AMBIL DATA SEBELUM DELETE ---
    db_building_before = buildingController.get_building_by_code(db, building_code=building_vcode) #
    if not db_building_before:
        raise HTTPException(status_code=404, detail="Building not found")
        
    # Konversi ke dict (Pake mode='json' buat fix datetime)
    jbefore = Building.model_validate(db_building_before).model_dump(mode='json')
    # ---------------------------------
    
    # Panggil controller asli lu. Ini akan me-return building yang SUDAH di-update
    updated_building = buildingController.delete_building(db=db, building_vcode=building_vcode, current_user=current_user) #
    
    if updated_building is None:
        # Ini harusnya gak kejadian kalo 'db_building_before' lolos, tapi buat jaga-jaga
        raise HTTPException(status_code=404, detail="Building not found or failed to delete")

    # --- BUAT 'jafter' DARI HASIL UPDATE ---
    # Konversi 'updated_role' (yang udah nstatus=0) ke dict
    jafter = Building.model_validate(updated_building).model_dump(mode='json')
    # --------------------------------------

    # --- LOG ACTIVITY (BACKGROUND) ---
    background_tasks.add_task(
        auditLogController.create_activity_log_task,
        nid_user=current_user.nid,
        action="DELETE", # Kita tetep pake action 'DELETE' biar jelas
        target_model="Building",
        target_identifier=building_vcode,
        jbefore=jbefore, # Data sebelum (nstatus=1)
        jafter=jafter, # <-- UBAH INI: Data sesudah (nstatus=0)
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    # ---------------------------------
    
    return # Return 204 No Content

@router.get("/all-for-dropdown/", response_model=schema.BuildingDropdownResponse)
def read_all_buildings_for_dropdown(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Mengambil semua data building aktif untuk keperluan dropdown.
    """
    check_adm_sa_only(db, current_user)
    buildings_data = buildingController.get_all_buildings_for_dropdown(db=db)
    return buildings_data

@router.get("/all-active-for-dropdown/", response_model=schema.BuildingDropdownResponse)
def read_all_active_buildings_for_dropdown(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Mengambil semua data building aktif untuk keperluan dropdown.
    """
    check_adm_sa_only(db, current_user)
    buildings_data = buildingController.get_all_active_buildings_for_dropdown(db=db)
    return buildings_data

@router.get("/get-all/", response_model=List[schema.Building])
def read_all_buildings_no_pagination(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    """
    Mengambil semua data building tanpa paginasi.
    """
    check_adm_sa_only(db, current_user)
    buildings = buildingController.get_all_buildings(db=db)
    return buildings["data"]