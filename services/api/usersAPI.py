from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Form # Tambah Request, Response, Form
# from fastapi.security import OAuth2PasswordRequestForm # Gak dipake lagi di /token
from sqlalchemy.orm import Session
from typing import List, Optional, Annotated 
from datetime import timedelta, datetime
from ..controller import userAccessController, auditLogController
from ..schemas import usersSchema as schema
from ..schemas.usersSchema import UserRegister, ActivationToken,  RequestPasswordReset, ResetPassword
from ..controller import usersController
from ..models import usersModel as models
from ..database import SessionLocal # Import SessionLocal untuk db_factory
import uuid
from ..schemas import userAccessSchema      # Pastikan ini ada
from ..models import userAccessModel, rolesModel # Buat query scope & role ID

from utils.token_refresh import RefreshConfig, refresh_access_cookie

from datetime import datetime
import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def to_wib(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return JAKARTA_TZ.localize(dt) if dt.tzinfo is None else dt.astimezone(JAKARTA_TZ)

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Settingan Cookie ---
# Ambil durasi dari controller (atau definisikan ulang di sini kalo mau)
ACCESS_TOKEN_COOKIE_EXPIRE_SECONDS = usersController.ACCESS_TOKEN_EXPIRE_MINUTES * 60
# Durasi panjang refresh token (dari controller)
REFRESH_TOKEN_COOKIE_EXPIRE_SECONDS = usersController.REFRESH_TOKEN_EXPIRE_DAYS * 60 * 60 * 24
# Definisikan durasi pendek refresh token (misal 1 hari)
SHORT_REFRESH_TOKEN_EXPIRE_SECONDS = 60 * 60 * 24 # 1 hari dalam detik

# Sesuaikan environment (development vs production)
COOKIE_SECURE = False # Ganti True kalo udah HTTPS
COOKIE_SAMESITE = 'lax' # 'strict' lebih aman tapi kadang kurang fleksibel -> ganti ke strict kalo udah production dan semua di HTTPS


cfg = RefreshConfig(
    access_cookie_key="access_token",
    refresh_cookie_key="refresh_token",
    access_cookie_path="/",
    refresh_cookie_path="/users/refresh_token",
    cookie_secure=COOKIE_SECURE,
    cookie_samesite=COOKIE_SAMESITE,
    access_cookie_max_age=ACCESS_TOKEN_COOKIE_EXPIRE_SECONDS,
)

@router.post("/token") # Hapus response_model=schema.TokenResponse
async def login_for_access_token(
    response: Response, # Inject Response object
    request: Request,
    # --- Terima form data secara manual ---
    username: str = Form(...), # Ambil username (email)
    password: str = Form(...), # Ambil password
    rememberMe: bool = Form(False), # Ambil rememberMe, default False
    # --- End form data manual ---
    db: Session = Depends(get_db)
):
    """
    Endpoint login. Autentikasi user, set HttpOnly cookies.
    Durasi refresh token cookie tergantung nilai rememberMe.
    """
    print(f"[API /token] Login attempt received for username: {username}")
    print(f"[API /token] Remember Me: {rememberMe}")

    try:
        # Autentikasi
        user = usersController.authenticate_user(db, email=username, request=request, password=password)
        if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Email atau password salah",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        
        try:
            db.commit() # Ini buat nyimpen log LOGIN_SUCCESS
        except Exception as commit_err:
            db.rollback()
            # Kalo log-nya gagal, gagalin login-nya juga
            print(f"[AUDIT LOG ERROR] Gagal commit log LOGIN_SUCCESS: {commit_err}")
            raise HTTPException(status_code=500, detail="Gagal mencatat log login.")

        # --- Tentukan durasi refresh token berdasarkan rememberMe ---
        if rememberMe:
            refresh_token_duration_seconds = REFRESH_TOKEN_COOKIE_EXPIRE_SECONDS
            refresh_token_expires_delta = timedelta(days=usersController.REFRESH_TOKEN_EXPIRE_DAYS)
            print(f"[API /token] Using long refresh token duration: {usersController.REFRESH_TOKEN_EXPIRE_DAYS} days")
        else:
            refresh_token_duration_seconds = SHORT_REFRESH_TOKEN_EXPIRE_SECONDS
            refresh_token_expires_delta = timedelta(seconds=SHORT_REFRESH_TOKEN_EXPIRE_SECONDS)
            print(f"[API /token] Using short refresh token duration: {SHORT_REFRESH_TOKEN_EXPIRE_SECONDS / 3600 / 24} days")
        # --- End Tentukan Durasi ---

        # Buat token (Access token tetep pendek)
        access_token_expires_delta = timedelta(minutes=usersController.ACCESS_TOKEN_EXPIRE_MINUTES)

        access_token = usersController.create_access_token(
            data={"sub": str(user.nid)}, expires_delta=access_token_expires_delta
        )
        refresh_token = usersController.create_refresh_token(
            data={"sub": str(user.nid)}, expires_delta=refresh_token_expires_delta # <-- Pake delta yg sesuai
        )

        print(f"[API /token] Token generated successfully for user {user.vemail} (ID: {user.nid})")

        # --- Set HTTP-Only Cookies ---
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=ACCESS_TOKEN_COOKIE_EXPIRE_SECONDS, # Access token tetep pendek
            expires=ACCESS_TOKEN_COOKIE_EXPIRE_SECONDS,
            path="/",
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE
        )
        print(f"[API /token] Access token cookie set (expires in {ACCESS_TOKEN_COOKIE_EXPIRE_SECONDS}s).")

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            max_age=refresh_token_duration_seconds, # <-- Pake durasi yg sesuai
            expires=refresh_token_duration_seconds, # <-- Pake durasi yg sesuai
            path="/users/refresh_token", # <-- Path spesifik
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE
        )
        print(f"[API /token] Refresh token cookie set (expires in {refresh_token_duration_seconds}s, path: /users/refresh_token).")
        # --- End Set Cookies ---

        user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=user.nid)
        base = schema.User.model_validate(user).model_dump()
        user_response = schema.UserWithRoles(**base, roles=user_roles)
        
        print(f"[API /token] Login successful for {user.vemail}. Returning user data.")
        
        return {"user": user_response, "refresh_token": refresh_token, "access_token": access_token, "token_type": "bearer", "access_expires_in": ACCESS_TOKEN_COOKIE_EXPIRE_SECONDS, "refresh_expires_in": refresh_token_duration_seconds}

    except ValueError as e:
         print(f"[API /token] Login failed for {username}: {str(e)}")
         raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    except Exception as e:
        error_message = str(e)
        print(f"[API /token] Unexpected error during login for {username}: {e}")
        
        if "401" in error_message or "Unauthorized" in error_message:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Email atau password salah."
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Terjadi kesalahan pada server saat mencoba login."
        )

@router.post("/refresh_token")
async def refresh_token_endpoint(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    return await refresh_access_cookie(
        request=request,
        response=response,
        db=db,
        users_controller=usersController,
        cfg=cfg,
    )

# --- Endpoint yang Membutuhkan Autentikasi ---
# Menggunakan dependency usersController.get_current_active_user_from_cookie

@router.get("/me", response_model=schema.UserWithRoles) 
async def read_users_me(
    current_user: models.User = Depends(usersController.get_current_active_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Mengembalikan data user yang sedang login (termasuk roles)."""
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)

    user_data_validated = schema.User.model_validate(current_user)

    response_data = schema.UserWithRoles(
        **user_data_validated.model_dump(),
        roles=user_roles
    )

    return response_data

@router.post("/admin-create", response_model=schema.User, status_code=status.HTTP_201_CREATED)
async def create_user_from_admin_panel(
    user_data: schema.UserCreateByAdmin,
    request: Request,
    db: Session = Depends(get_db),
    current_user: schema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Membuat user baru oleh admin (membutuhkan hak akses)."""
    # ... (Logika print & permission check existing biarkan saja) ...
    
    # [Existing Code] Permission Check
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    allowed_roles = {"SA", "ADM"}
    if not any(role in allowed_roles for role in user_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk membuat pengguna baru."
        )

    try:
        user_data.vcreated_by = current_user.vcode
        
        # 1. Create User (Existing)
        new_user = await usersController.create_user_by_admin(
            db=db, user_data=user_data, request=request, app=request.app, db_factory=SessionLocal
        )
        
        # --- [LOGIC BARU: AUTO ASSIGN VISITOR ACCESS] ---
        # Cek apakah Creator adalah ADMIN (ADM) dan punya Departemen
        admin_access = db.query(userAccessModel.UserAccess).join(
            rolesModel.Role, userAccessModel.UserAccess.nid_role == rolesModel.Role.nid
        ).filter(
            userAccessModel.UserAccess.nid_user == current_user.nid,
            rolesModel.Role.vcode == 'ADM',
            userAccessModel.UserAccess.nstatus == 1
        ).first()

        # Jika yang bikin adalah Admin Department
        if admin_access and admin_access.nid_department:
            print(f"[AutoAccess] Admin Dept ID {admin_access.nid_department} detected. Assigning VSTR role...")
            
            # Cari ID Role 'VSTR' (Visitor)
            visitor_role = db.query(rolesModel.Role).filter(rolesModel.Role.vcode == 'VSTR').first()
            
            if visitor_role:
                # Generate vcode unik untuk UserAccess
                ua_vcode = f"UACC-{uuid.uuid4().hex[:8].upper()}"
                
                # Siapkan data UserAccess
                new_access_data = userAccessSchema.UserAccessCreate(
                    vcode=ua_vcode,
                    nid_user=new_user.nid,       # User yang baru dibuat
                    nid_role=visitor_role.nid,   # Role Visitor
                    nid_department=admin_access.nid_department, # Dept si Admin
                    nid_lab=None,                # Default kosong dulu
                    vcreated_by=current_user.vcode
                )
                
                # Create Access via Controller
                userAccessController.create_user_access(db=db, user_access=new_access_data)
                print(f"[AutoAccess] Success: User {new_user.vemail} assigned as VSTR in Dept {admin_access.nid_department}")
            else:
                print("[AutoAccess] Warning: Role 'VSTR' not found in database. Auto-assign failed.")
        # ------------------------------------------------

        print(f"[API /admin-create] User {new_user.vemail} created successfully.")
        return new_user

    except ValueError as e:
        print(f"[API /admin-create] Failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
         print(f"[API /admin-create] Unexpected error: {e}")
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal membuat pengguna.")


@router.post("/register", response_model=schema.User, status_code=status.HTTP_201_CREATED)
async def register_user_publicly(
    user_data: UserRegister, # <-- Pake schema baru kita
    request: Request,
    db: Session = Depends(get_db)
):
    """Endpoint publik untuk user registrasi baru."""
    print(f"[API /register] Request registrasi diterima untuk email: {user_data.vemail}")
    try:
        # Panggil controller baru kita
        new_user = await usersController.register_new_user(
            db=db, 
            user_data=user_data, 
            app=request.app, 
            request=request,
            db_factory=SessionLocal
        )
        print(f"[API /register] User {new_user.vemail} berhasil dibuat (Pending).")
        return new_user
    except ValueError as e:
        error_detail = str(e)
        print(f"[API /register] Gagal: {error_detail}")
        # Cek error spesifik buat HTTP status code yg pas
        if "sudah terdaftar" in error_detail or "sudah digunakan" in error_detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail)
    except Exception as e:
         print(f"[API /register] Unexpected error: {e}")
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal mendaftarkan pengguna.")


@router.put("/{user_vcode}", response_model=schema.User)
async def update_existing_user(
    user_vcode: str,
    user_update_data: schema.UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: schema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Mengupdate data user (membutuhkan hak akses atau user itu sendiri)."""
    print(f"[API PUT /users/{user_vcode}] Request received from user: {current_user.vemail}")
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    print(f"[API PUT /users/{user_vcode}] User roles: {user_roles}")
    
    # --- AMBIL INFO USER TARGET (UDAH ADA) ---
    target_user = usersController.get_user_by_code(db, user_code=user_vcode)
    if not target_user:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pengguna yang akan diupdate tidak ditemukan.")
    
    # Simpen info lama buat logging
    target_user_nid = target_user.nid
    target_user_email = target_user.vemail
    # ----------------------------------------

    is_updating_self = current_user.vcode == user_vcode
    allowed_admin_roles = {"SA", 'ADM'} # Sesuaikan
    is_allowed_admin = any(role in allowed_admin_roles for role in user_roles)

    if not is_updating_self and not is_allowed_admin:
        print(f"[API PUT /users/{user_vcode}] Forbidden: User {current_user.vemail} cannot update user {user_vcode}.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk mengupdate pengguna ini."
        )

    try:
        user_update_data.vmodified_by = current_user.vcode
        db_user = await usersController.update_user(
            db=db, user_vcode=user_vcode, user=user_update_data, app=request.app, db_factory=SessionLocal, request=request
        )
        if db_user is None:
            print(f"[API PUT /users/{user_vcode}] Update failed: User not found.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        # --- [INI TAMBAHANNYA] ---
        # (Kita log ini walaupun user-nya update data diri sendiri, 
        #  tapi detailnya bisa dibedain dari message log-nya)
        log_details = ""
        if is_updating_self:
            log_details = f"User {current_user.vemail} (NID: {current_user.nid}) memperbarui datanya sendiri."
        else:
            log_details = f"Admin {current_user.vemail} memperbarui data akun: {target_user_email} (NID: {target_user_nid})"

        try:
            auditLogController.create_security_log(
                db=db, 
                nid_user=current_user.nid, # NID user yg melakukan aksi
                action="ACCOUNT_UPDATED", 
                request=request, 
                details=log_details
            )
            db.commit() # Commit log-nya
            print(f"[AUDIT LOG] Security log committed for ACCOUNT_UPDATED.")
        except Exception as log_err:
            db.rollback()
            print(f"[AUDIT LOG ERROR] Gagal menyimpan security log update: {log_err}")
        # ---------------------------

        print(f"[API PUT /users/{user_vcode}] User updated successfully by {current_user.vemail}.")
        return db_user
        
    except ValueError as e:
        print(f"[API PUT /users/{user_vcode}] Update failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
         print(f"[API PUT /users/{user_vcode}] Unexpected error: {e}")
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal mengupdate pengguna.")


@router.delete("/{user_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_user(
    user_vcode: str,
    response: Response, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: schema.User = Depends(usersController.get_current_active_user_from_cookie),
):
    """Melakukan soft delete user (membutuhkan hak akses)."""
    print(f"[API DELETE /users/{user_vcode}] Request received from user: {current_user.vemail}")
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    print(f"[API DELETE /users/{user_vcode}] User roles: {user_roles}")

    allowed_roles = {"SA", 'ADM'} # Sesuaikan
    if not any(role in allowed_roles for role in user_roles):
         print(f"[API DELETE /users/{user_vcode}] Forbidden: User {current_user.vemail} cannot delete users.")
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Anda tidak punya hak akses untuk menghapus pengguna."
         )

    if current_user.vcode == user_vcode:
         print(f"[API DELETE /users/{user_vcode}] Forbidden: User cannot delete self.")
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST,
             detail="Tidak dapat menghapus akun sendiri."
         )

    # --- 2. AMBIL INFO USER TARGET SEBELUM DELETE ---
    target_user = usersController.get_user_by_code(db, user_code=user_vcode)
    if not target_user:
        print(f"[API DELETE /users/{user_vcode}] Delete failed: User not found (pre-check).")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pengguna tidak ditemukan.")
    
    # Simpen data user target buat logging
    target_user_nid = target_user.nid 
    target_user_email = target_user.vemail
    # ------------------------------------------------

    # Panggil controller buat soft delete
    deleted_user = usersController.delete_user(db=db, user_vcode=user_vcode, current_user=current_user.vcode)

    if deleted_user is None or deleted_user.nstatus != 0:
        print(f"[API DELETE /users/{user_vcode}] Delete failed: User not found or internal error during delete.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pengguna tidak ditemukan atau gagal dihapus.")
    
    # --- 3. TAMBAHIN SECURITY LOG ---
    try:
        auditLogController.create_security_log(
            db=db, 
            nid_user=current_user.nid, # NID Admin yg nge-delete
            action="ACCOUNT_DEACTIVATED", # Aksi yang lebih spesifik
            request=request, 
            details=f"Admin {current_user.vemail} menonaktifkan akun: {target_user_email} (NID: {target_user_nid})"
        )
        db.commit() # <-- 4. COMMIT LOG-NYA
        print(f"[AUDIT LOG] Security log committed for ACCOUNT_DEACTIVATED.")
    except Exception as log_err:
        db.rollback()
        # Sebaiknya jangan gagalin seluruh proses kalo log gagal, tapi catet errornya
        print(f"[AUDIT LOG ERROR] Gagal menyimpan security log: {log_err}")
    # --------------------------------

    print(f"[API DELETE /users/{user_vcode}] User soft deleted successfully by {current_user.vemail}.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/", response_model=schema.UserResponse)
def read_all_users(
    skip: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    nstatus: Optional[int] = None,
    name: Optional[str] = None,
    email: Optional[str] = None,
    code: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: schema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Mengambil daftar user (membutuhkan hak akses)."""
    print(f"[API GET /users/] Request received from user: {current_user.vemail}")
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    print(f"[API GET /users/] User roles: {user_roles}")

    allowed_roles = {"SA", "ADM"} 
    if not any(role in allowed_roles for role in user_roles):
        print(f"[API GET /users/] Forbidden: User {current_user.vemail} cannot view user list.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk melihat daftar pengguna."
        )

    users_data = usersController.get_users(
        db=db, 
        current_user=current_user, 
        skip=skip, 
        limit=limit, 
        search=search,
        nstatus=nstatus, 
        vname=name, 
        vemail=email, 
        vcode=code
    )

    print(f"[API GET /users/] Returning {len(users_data['data'])} users (Total: {users_data['total']}).")
    return users_data

@router.get("/{user_id}", response_model=schema.User)
def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: schema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Mengambil detail user berdasarkan ID (membutuhkan hak akses)."""
    print(f"[API GET /users/{user_id}] Request received from user: {current_user.vemail}")
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    print(f"[API GET /users/{user_id}] User roles: {user_roles}")

    allowed_roles = {"SA", "ADM"} # Sesuaikan
    is_allowed_admin = any(role in allowed_roles for role in user_roles)
    is_requesting_self = current_user.nid == user_id

    if not is_allowed_admin and not is_requesting_self:
         print(f"[API GET /users/{user_id}] Forbidden: User {current_user.vemail} cannot view user ID {user_id}.")
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Anda tidak punya hak akses untuk melihat pengguna ini."
         )

    user = usersController.get_user(db=db, user_id=user_id)
    if user is None:
        print(f"[API GET /users/{user_id}] Failed: User not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pengguna tidak ditemukan")
    print(f"[API GET /users/{user_id}] User found: {user.vemail}.")
    return user


@router.get("/all-for-dropdown/", response_model=schema.UserDropdownResponse)
def read_all_users_for_dropdown(
    db: Session = Depends(get_db),
    current_user: schema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Mengambil daftar user aktif untuk dropdown (membutuhkan hak akses)."""
    print(f"[API /all-for-dropdown/] Request received from user: {current_user.vemail}")
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    print(f"[API /all-for-dropdown/] User roles: {user_roles}")

    allowed_roles = {"SA", "ADM"} # Sesuaikan
    if not any(role in allowed_roles for role in user_roles):
         print(f"[API /all-for-dropdown/] Forbidden: User {current_user.vemail} cannot access dropdown list.")
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Anda tidak punya hak akses untuk data ini."
         )

    users_data = usersController.get_all_users_for_dropdown(db=db)
    print(f"[API /all-for-dropdown/] Returning {len(users_data['data'])} active users for dropdown.")
    return users_data

@router.get("/scope-all-for-dropdown/", response_model=schema.UserDropdownResponse)
def read_scope_all_users_for_dropdown(
    db: Session = Depends(get_db),
    current_user: schema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    [SCOPED] Semua User (Active/Inactive) sesuai Departemen Admin.
    """
    # Cek hak akses
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if not any(role in {"SA", "ADM"} for role in user_roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
    
    users_data = usersController.get_scoped_users_for_dropdown(db=db, current_user=current_user)
    return users_data

@router.get("/scope-active-for-dropdown/", response_model=schema.UserDropdownResponse)
def read_scope_active_users_for_dropdown(
    db: Session = Depends(get_db),
    current_user: schema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    [SCOPED] User Aktif Saja sesuai Departemen Admin.
    """
    # Cek hak akses
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if not any(role in {"SA", "ADM"} for role in user_roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
    
    users_data = usersController.get_scoped_active_users_for_dropdown(db=db, current_user=current_user)
    return users_data

@router.get("/all-active-for-dropdown/", response_model=schema.UserDropdownResponse)
def read_all_users_for_dropdown(
    db: Session = Depends(get_db),
    current_user: schema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """Mengambil daftar user aktif untuk dropdown (membutuhkan hak akses)."""
    print(f"[API /all-active-for-dropdown/] Request received from user: {current_user.vemail}")
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    print(f"[API /all-active-for-dropdown/] User roles: {user_roles}")

    allowed_roles = {"SA", "ADM"} # Sesuaikan
    if not any(role in allowed_roles for role in user_roles):
         print(f"[API /all-active-for-dropdown/] Forbidden: User {current_user.vemail} cannot access dropdown list.")
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Anda tidak punya hak akses untuk data ini."
         )

    users_data = usersController.get_all_active_users_for_dropdown(db=db)
    print(f"[API /all-active-for-dropdown/] Returning {len(users_data['data'])} active users for dropdown.")
    return users_data

# --- Endpoint Publik (tidak butuh autentikasi) ---

@router.post("/set-initial-password", response_model=schema.User)
def set_user_initial_password(password_data: schema.SetInitialPassword, request: Request, db: Session = Depends(get_db)):
    """Endpoint publik untuk user set password awal pakai token aktivasi."""
    print(f"[API /set-initial-password] Request received for token: {password_data.token[:5]}...")
    try:
        updated_user = usersController.set_initial_password(db=db, request=request, password_data=password_data)
        print(f"[API /set-initial-password] Password set successfully for user: {updated_user.vemail}")
        return updated_user
    except ValueError as e:
        error_detail = str(e)
        print(f"[API /set-initial-password] Failed: {error_detail}")
        status_code = status.HTTP_400_BAD_REQUEST
        if "tidak valid" in error_detail or "kedaluwarsa" in error_detail or "digunakan" in error_detail or "tidak ditemukan" in error_detail:
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=error_detail)
    except Exception as e:
         print(f"[API /set-initial-password] Unexpected error: {e}")
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal mengatur password.")


@router.post("/resend-activation/{user_vcode}", status_code=status.HTTP_200_OK)
async def resend_user_activation(user_vcode: str, request: Request, db: Session = Depends(get_db)):
    """Endpoint publik untuk minta kirim ulang email aktivasi."""
    print(f"[API /resend-activation/{user_vcode}] Request received.")
    try:
        response_message = await usersController.resend_activation_email(
            db=db, user_vcode=user_vcode, app=request.app, db_factory=SessionLocal
        )
        print(f"[API /resend-activation/{user_vcode}] Email resent successfully.")
        return response_message
    except ValueError as e:
        error_detail = str(e)
        print(f"[API /resend-activation/{user_vcode}] Failed: {error_detail}")
        status_code = status.HTTP_400_BAD_REQUEST
        if "tidak ditemukan" in error_detail:
             status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=error_detail)
    except Exception as e:
        print(f"[API /resend-activation/{user_vcode}] Unexpected error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gagal mengirim ulang email: {str(e)}")


@router.get("/validate-activation-token/{token}")
def validate_activation_token_endpoint(token: str, db: Session = Depends(get_db)):
    """Endpoint publik untuk cek validitas token aktivasi (buat UI)."""
    print(f"[API /validate-activation-token/] Request received for token: {token[:5]}...")
    result = usersController.verify_activation_token(db=db, token=token)
    if not result["valid"]:
        print(f"[API /validate-activation-token/] Token invalid: {result['reason']}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["reason"])
    print(f"[API /validate-activation-token/] Token valid.")
    return result


@router.get("/verify-email-change/{token}", response_model=schema.User)
def verify_user_email_change(token: str, request: Request, db: Session = Depends(get_db)):
    """Endpoint publik untuk verifikasi perubahan email via token."""
    print(f"[API /verify-email-change/] Request received for token: {token[:5]}...")
    try:
        updated_user = usersController.verify_and_update_email(db=db, token=token, request=request)
        print(f"[API /verify-email-change/] Email change verified successfully for user: {updated_user.vemail}")
        return updated_user
    except ValueError as e:
        error_detail = str(e)
        print(f"[API /verify-email-change/] Failed: {error_detail}")
        status_code = status.HTTP_400_BAD_REQUEST
        if "tidak valid" in error_detail or "kedaluwarsa" in error_detail or "digunakan" in error_detail or "tidak ditemukan" in error_detail:
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=error_detail)
    except Exception as e:
         print(f"[API /verify-email-change/] Unexpected error: {e}")
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal verifikasi email.")

# Endpoint logout (opsional tapi bagus)
@router.post("/logout")
async def logout(response: Response, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(usersController.get_current_active_user_from_cookie)):
    """Menghapus cookie access dan refresh token."""
    print("[API /logout] Logout request received. Deleting token cookies.")
    try:
        auditLogController.create_security_log(
            db=db, nid_user=current_user.nid, action="LOGOUT", request=request
        )
        db.commit() # Commit log-nya
    except Exception as e:
        print(f"[AUDIT LOG ERROR] Gagal nyimpen logout log: {e}")
        db.rollback()

    response.delete_cookie("access_token", path="/", secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)
    response.delete_cookie("refresh_token", path="/users/refresh_token", secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)
    return {"message": "Logout successful"}


@router.post("/activate-account", response_model=schema.User)
def activate_newly_registered_user(
    token_data: ActivationToken,
    request: Request,
    db: Session = Depends(get_db)
):
    """Endpoint publik untuk aktivasi akun yang baru diregistrasi (status 2 -> 1)."""
    print(f"[API /activate-account] Request aktivasi diterima untuk token: {token_data.token[:5]}...")
    try:
        # Panggil controller aktivasi baru kita
        activated_user = usersController.activate_registered_user(db=db, request=request, token=token_data.token)
        print(f"[API /activate-account] Akun berhasil diaktivasi untuk: {activated_user.vemail}")
        return activated_user
    except ValueError as e:
        error_detail = str(e)
        print(f"[API /activate-account] Gagal: {error_detail}")
        status_code = status.HTTP_400_BAD_REQUEST
        if "tidak valid" in error_detail or "kedaluwarsa" in error_detail or "digunakan" in error_detail or "tidak ditemukan" in error_detail:
            status_code = status.HTTP_404_NOT_FOUND
        elif "sudah aktif" in error_detail:
             status_code = status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=error_detail)
    except Exception as e:
         print(f"[API /activate-account] Unexpected error: {e}")
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal mengaktifkan akun.")

@router.post("/request-password-reset", status_code=status.HTTP_200_OK)
async def request_password_reset_endpoint(
    request_data: RequestPasswordReset, 
    request: Request,
    db: Session = Depends(get_db)
):
    """Endpoint publik untuk minta kirim email reset password."""
    print(f"[API /request-password-reset] Request received for email: {request_data.email}")
    try:
        response_message = await usersController.request_password_reset(
            db=db, 
            email=request_data.email, 
            request=request,
            app=request.app, 
            db_factory=SessionLocal
        )
        return response_message
    except Exception as e:
        print(f"[API /request-password-reset] Unexpected error: {e}")
        # Tetap return sukses palsu biar aman
        return {"message": "Jika email Anda terdaftar, instruksi reset password akan dikirim."}

@router.get("/validate-reset-token/{token}")
def validate_reset_token_endpoint(token: str, db: Session = Depends(get_db)):
    """Endpoint publik untuk cek validitas token reset password (buat UI)."""
    print(f"[API /validate-reset-token/] Request received for token: {token[:5]}...")
    result = usersController.verify_reset_token(db=db, token=token)
    if not result["valid"]:
        print(f"[API /validate-reset-token/] Token invalid: {result['reason']}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["reason"])
    print(f"[API /validate-reset-token/] Token valid.")
    return result

@router.post("/reset-password", response_model=schema.User)
def reset_user_password(password_data: ResetPassword,request: Request, db: Session = Depends(get_db)):
    """Endpoint publik untuk user set password baru pakai token reset."""
    print(f"[API /reset-password] Request received for token: {password_data.token[:5]}...")
    try:
        updated_user = usersController.reset_password(db=db, password_data=password_data, request=request)
        print(f"[API /reset-password] Password reset successfully for user: {updated_user.vemail}")
        return updated_user
    except ValueError as e:
        error_detail = str(e)
        print(f"[API /reset-password] Failed: {error_detail}")
        status_code = status.HTTP_400_BAD_REQUEST
        if "tidak valid" in error_detail or "kedaluwarsa" in error_detail or "digunakan" in error_detail or "tidak ditemukan" in error_detail:
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=error_detail)
    except Exception as e:
         print(f"[API /reset-password] Unexpected error: {e}")
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal mengatur password baru.")
     
     