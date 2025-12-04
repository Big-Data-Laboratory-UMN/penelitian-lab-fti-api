from sqlalchemy import or_, UniqueConstraint, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from ..models import buildingModel as models
from ..schemas import buildingSchema as schema, usersSchema
from ..models import userAccessModel

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


def get_building_by_code_and_name(db: Session, vcode: str, vname: str):
    """
    Cari building berdasarkan kombinasi vcode dan vname.
    """
    return db.query(models.Building).filter(
        and_(
            models.Building.vcode == vcode,
            models.Building.vname == vname
        )
    ).first()


def get_building_by_code(db: Session, building_code: str):
    """
    Fungsi untuk mencari building berdasarkan vcode (unique).
    """
    return db.query(models.Building).filter(models.Building.vcode == building_code).first()


def get_building(db: Session, building_id: int):
    """
    Fungsi ini cuma fokus nyari satu building berdasarkan ID-nya.
    """
    return db.query(models.Building).filter(models.Building.nid == building_id).first()


def create_building(db: Session, building: schema.BuildingCreate, current_user: usersSchema.User):
    """
    Fungsi untuk membuat building baru.
    Cegah duplikasi (vcode, vname) + race condition.
    """
    db_building = models.Building(**building.model_dump())
    db_building.vcreated_by = current_user.vcode
    db_building.dsort_at = now_wib()

    try:
        db.add(db_building)
        db.commit()
        db.refresh(db_building)
        return db_building
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


def update_building(db: Session, building_vcode: str, building: schema.BuildingUpdate, current_user: usersSchema.User):
    """
    Fungsi untuk mengupdate building yang sudah ada berdasarkan VCODE.
    """
    db_building = get_building_by_code(db, building_code=building_vcode)
    if not db_building:
        return None

    db_building.vcode = building.vcode
    db_building.vname = building.vname
    db_building.vdesc = building.vdesc
    db_building.nstatus = building.nstatus
    db_building.vmodified_by = current_user.vcode
    db_building.dsort_at = now_wib()

    try:
        db.commit()
        db.refresh(db_building)
        return db_building
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

def get_buildings(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    vname: str | None = None,
    vcode: str | None = None,
    vdesc: str | None = None,
    nstatus: int | None = None
):
    """
    Mengambil data building dengan paginasi, total data, dan filter pencarian.
    """
    query = db.query(models.Building)

    if search:
        search_filter = or_(
            models.Building.vname.ilike(f"%{search}%"),
            models.Building.vcode.ilike(f"%{search}%"),
            models.Building.vdesc.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    if vname:
        query = query.filter(models.Building.vname.ilike(f"%{vname}%"))
    if vcode:
        query = query.filter(models.Building.vcode.ilike(f"%{vcode}%"))
    if vdesc:
        query = query.filter(models.Building.vdesc.ilike(f"%{vdesc}%"))
    if nstatus is not None:
        query = query.filter(models.Building.nstatus == nstatus)

    total = query.count()

    # Urutkan berdasarkan waktu terakhir diubah/dibuat
    query = query.order_by(models.Building.dsort_at.desc())

    data = query.offset(skip).limit(limit).all()

    return {"data": data, "total": total}


def delete_building(db: Session, building_vcode: str, current_user: usersSchema.User):
    """
    Melakukan soft delete berdasarkan VCODE dengan mengubah nstatus menjadi 0 (Inactive).
    """
    db_building = db.query(models.Building).filter(models.Building.vcode == building_vcode).first()
    if db_building:
        db_building.nstatus = 0
        db_building.vmodified_by = current_user.vcode
        db_building.dsort_at = now_wib()
        db.commit()
        db.refresh(db_building)
    return db_building


def get_all_active_buildings_for_dropdown(db: Session):
    """
    Mengambil semua data building yang aktif (nstatus=1) untuk dropdown,
    tanpa paginasi.
    """
    buildings = (
        db.query(models.Building)
        .filter(models.Building.nstatus == 1)
        .order_by(models.Building.vname)
        .all()
    )
    return {"data": buildings}

def get_all_buildings_for_dropdown(db: Session):
    """
    Mengambil semua data building yang aktif (nstatus=1) untuk dropdown,
    tanpa paginasi.
    """
    buildings = (
        db.query(models.Building)
        .order_by(models.Building.vname)
        .all()
    )
    return {"data": buildings}

def get_scoped_buildings_for_dropdown(db: Session, current_user: usersSchema.User):
    """
    [SCOPED] Mengambil SEMUA building (Active/Inactive) dengan filter logic:
    - SA: All
    - ADM: Only VSTR & PIC
    """
    return _get_buildings_by_scope_logic(db, current_user, only_active=False)

def get_scoped_active_buildings_for_dropdown(db: Session, current_user: usersSchema.User):
    """
    [SCOPED] Mengambil building AKTIF saja dengan filter logic:
    - SA: All Active
    - ADM: Only Active VSTR & PIC
    """
    return _get_buildings_by_scope_logic(db, current_user, only_active=True)


# --- Helper Internal Logic ---
def _get_buildings_by_scope_logic(db: Session, current_user: usersSchema.User, only_active: bool):
    # 1. Cek apakah user adalah SA (Superadmin)
    is_sa = db.query(userAccessModel.UserAccess).join(
        models.Building, userAccessModel.UserAccess.nid_building == models.Building.nid
    ).filter(
        userAccessModel.UserAccess.nid_user == current_user.nid,
        models.Building.vcode == 'SA',
        userAccessModel.UserAccess.nstatus == 1 # Pastikan akses SA-nya aktif
    ).first()

    # 2. Base Query
    query = db.query(models.Building)
    
    # Filter Active Only jika diminta
    if only_active:
        query = query.filter(models.Building.nstatus == 1)

    # 3. Apply Scope Filter (Jika BUKAN SA)
    if not is_sa:
        # Logic Admin: Hanya boleh lihat building 'Visitor' dan 'PIC'
        query = query.filter(models.Building.vcode.in_(['VSTR', 'PIC']))

    # 4. Order & Return
    query = query.order_by(models.Building.vname.asc())
    data = query.all()
    
    return {"data": data}