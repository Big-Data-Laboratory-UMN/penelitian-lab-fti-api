from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Form
from sqlalchemy.orm import Session
from typing import Optional
from datetime import timedelta, datetime
import uuid
import os
import logging

from ..controller import userAccessController, auditLogController
from ..schemas import usersSchema as schema
from ..schemas.usersSchema import (
    UserRegister, ActivationToken, RequestPasswordReset, ResetPassword
)
from ..controller import usersController
from ..models import usersModel as models
from ..database import SessionLocal
from ..schemas import userAccessSchema
from ..models import userAccessModel, rolesModel
from ..models.tokenModel import Token

from utils.token_refresh import RefreshConfig, refresh_access_cookie

import pytz

# ------------------------------------------------------------------
# Logger
# ------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Timezone helper
# ------------------------------------------------------------------
JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def to_wib(dt: datetime) -> datetime:
    if dt is None:
        return dt
    return JAKARTA_TZ.localize(dt) if dt.tzinfo is None else dt.astimezone(JAKARTA_TZ)

# ------------------------------------------------------------------
# Role constants – hindari string literal rawan typo
# ------------------------------------------------------------------
ALLOWED_ADMIN_ROLES = frozenset({"SA", "ADM"})

# ------------------------------------------------------------------
# Cookie configuration dengan validasi SameSite
# ------------------------------------------------------------------
ACCESS_TOKEN_COOKIE_EXPIRE_SECONDS = usersController.ACCESS_TOKEN_EXPIRE_MINUTES * 60
REFRESH_TOKEN_COOKIE_EXPIRE_SECONDS = usersController.REFRESH_TOKEN_EXPIRE_DAYS * 60 * 60 * 24
SHORT_REFRESH_TOKEN_EXPIRE_SECONDS = 60 * 60 * 24          # 1 hari

COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() in ("true", "1", "yes")
_raw_samesite = os.getenv("COOKIE_SAMESITE", "lax").lower()
if _raw_samesite in ("lax", "strict", "none"):
    COOKIE_SAMESITE = _raw_samesite
else:
    logger.warning(
        "COOKIE_SAMESITE=%s tidak valid, fallback ke 'lax'", _raw_samesite
    )
    COOKIE_SAMESITE = "lax"

if COOKIE_SAMESITE == "none" and not COOKIE_SECURE:
    logger.warning(
        "COOKIE_SAMESITE='none' tetapi COOKIE_SECURE=False, "
        "memaksa secure=True"
    )
    COOKIE_SECURE = True

# 🔥 Default None: cookie mengikuti host request (paling aman di dev).
#    Di production, set env COOKIE_DOMAIN (misal "labfti.umn.ac.id").
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN")  # default None

cfg = RefreshConfig(
    access_cookie_key="access_token",
    refresh_cookie_key="refresh_token",
    access_cookie_path="/",
    refresh_cookie_path="/users/refresh_token",
    cookie_secure=COOKIE_SECURE,
    cookie_samesite=COOKIE_SAMESITE,
    access_cookie_max_age=ACCESS_TOKEN_COOKIE_EXPIRE_SECONDS,
)

# ------------------------------------------------------------------
# Router
# ------------------------------------------------------------------
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

# ------------------------------------------------------------------
# Helper: ambil IP asli (di belakang proxy)
# ------------------------------------------------------------------
def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Bisa berisi beberapa IP, ambil yang pertama
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

# ------------------------------------------------------------------
# LOGIN
# ------------------------------------------------------------------
@router.post("/token")
async def login_for_access_token(
    response: Response,
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    rememberMe: bool = Form(False),
    db: Session = Depends(get_db),
):
    """
    Endpoint login. Autentikasi user, set HttpOnly cookies.
    Tidak mengembalikan token di response body (keamanan XSS).
    """
    logger.info("Login attempt untuk username: %s, rememberMe: %s", username, rememberMe)

    try:
        # 1. Autentikasi
        user = usersController.authenticate_user(
            db, email=username, request=request, password=password
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email atau password salah",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 2. Catat log LOGIN_SUCCESS (belum commit)
        auditLogController.create_security_log(
            db=db,
            nid_user=user.nid,
            action="LOGIN_SUCCESS",
            request=request,
            details=f"User {user.vemail} berhasil login.",
        )

        # 3. Durasi token berdasarkan rememberMe
        if rememberMe:
            refresh_duration_s = REFRESH_TOKEN_COOKIE_EXPIRE_SECONDS
            refresh_delta = timedelta(days=usersController.REFRESH_TOKEN_EXPIRE_DAYS)
            logger.debug("Menggunakan long refresh token: %d detik", refresh_duration_s)
        else:
            refresh_duration_s = SHORT_REFRESH_TOKEN_EXPIRE_SECONDS
            refresh_delta = timedelta(seconds=SHORT_REFRESH_TOKEN_EXPIRE_SECONDS)
            logger.debug("Menggunakan short refresh token: %d detik", refresh_duration_s)

        access_delta = timedelta(minutes=usersController.ACCESS_TOKEN_EXPIRE_MINUTES)

        # 4. Buat token
        access_token = usersController.create_access_token(
            data={"sub": str(user.nid)}, expires_delta=access_delta
        )
        refresh_token = usersController.create_refresh_token(
            data={"sub": str(user.nid)}, expires_delta=refresh_delta
        )
        logger.info("Token berhasil dibuat untuk user %s (ID: %s)", user.vemail, user.nid)

        # 5. Invalidasi session lama (satu user hanya satu session aktif)
        db.query(Token).filter(
            Token.nid_user == user.nid,
            Token.ntoken_type == 2,          # tipe login session
            Token.nstatus == 1               # masih aktif
        ).update({
            "nstatus": 0,
            "dmodified_at": to_wib(datetime.now(JAKARTA_TZ)),
        })

        # 6. Simpan session baru
        ip_address = get_client_ip(request)
        access_expire_dt = to_wib(datetime.now(JAKARTA_TZ)) + timedelta(seconds=ACCESS_TOKEN_COOKIE_EXPIRE_SECONDS)
        refresh_expire_dt = to_wib(datetime.now(JAKARTA_TZ)) + timedelta(seconds=refresh_duration_s)

        db_token = Token(
            nid_user=user.nid,
            ntoken_type=2,
            vcode=str(uuid.uuid4()),
            vaccess_token=access_token,
            vrefresh_token=refresh_token,
            dexpires_at=access_expire_dt,
            drefresh_expire_at=refresh_expire_dt,
            nstatus=1,
            vip_address=ip_address,
            vbrowser_info=request.headers.get("user-agent"),
        )
        db.add(db_token)

        # 7. Commit seluruh transaksi (log + session)
        db.commit()
        logger.info("Transaksi login berhasil di-commit untuk %s", user.vemail)

        # 8. Set HttpOnly cookies
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=ACCESS_TOKEN_COOKIE_EXPIRE_SECONDS,
            expires=ACCESS_TOKEN_COOKIE_EXPIRE_SECONDS,
            path="/",
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            domain=COOKIE_DOMAIN,
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            max_age=refresh_duration_s,
            expires=refresh_duration_s,
            path="/users/refresh_token",
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            domain=COOKIE_DOMAIN,
        )
        logger.info("Cookie access & refresh berhasil diset untuk %s", user.vemail)

        # 9. Response tanpa token (hanya informasi non‑sensitif)
        user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=user.nid)
        base = schema.User.model_validate(user).model_dump()
        user_response = schema.UserWithRoles(**base, roles=user_roles)

        return {
            "user": user_response,
            "token_type": "bearer",
            "access_expires_in": ACCESS_TOKEN_COOKIE_EXPIRE_SECONDS,
            "refresh_expires_in": refresh_duration_s,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("Unexpected error saat login user %s: %s", username, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Terjadi kesalahan pada server saat mencoba login.",
        )

# ------------------------------------------------------------------
# REFRESH TOKEN (sekarang dengan logging + error handling)
# ------------------------------------------------------------------
@router.post("/refresh_token")
async def refresh_token_endpoint(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    try:
        logger.debug("Refresh token attempt from %s", get_client_ip(request))
        result = await refresh_access_cookie(
            request=request,
            response=response,
            db=db,
            users_controller=usersController,
            cfg=cfg,
        )
        logger.info("Refresh token berhasil")
        return result
    except Exception as e:
        logger.exception("Refresh token error: %s", e)
        raise

# ------------------------------------------------------------------
# ENDPOINT TERPROTEKSI
# ------------------------------------------------------------------

@router.get("/me", response_model=schema.UserWithRoles)
async def read_users_me(
    current_user: models.User = Depends(usersController.get_current_active_user_from_cookie),
    db: Session = Depends(get_db)
):
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    user_data = schema.User.model_validate(current_user).model_dump()
    return schema.UserWithRoles(**user_data, roles=user_roles)


@router.post("/admin-create", response_model=schema.User, status_code=status.HTTP_201_CREATED)
async def create_user_from_admin_panel(
    user_data: schema.UserCreateByAdmin,
    request: Request,
    db: Session = Depends(get_db),
    current_user: schema.User = Depends(usersController.get_current_active_user_from_cookie),
):
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if not any(role in ALLOWED_ADMIN_ROLES for role in user_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk membuat pengguna baru.",
        )

    try:
        user_data.vcreated_by = current_user.vcode
        new_user = await usersController.create_user_by_admin(
            db=db, user_data=user_data, request=request, app=request.app, db_factory=SessionLocal
        )

        # Jika admin department, auto‑assign role Visitor (VSTR)
        admin_access = (
            db.query(userAccessModel.UserAccess)
            .join(rolesModel.Role, userAccessModel.UserAccess.nid_role == rolesModel.Role.nid)
            .filter(
                userAccessModel.UserAccess.nid_user == current_user.nid,
                rolesModel.Role.vcode == "ADM",
                userAccessModel.UserAccess.nstatus == 1,
            )
            .first()
        )

        if admin_access and admin_access.nid_department:
            visitor_role = db.query(rolesModel.Role).filter(rolesModel.Role.vcode == "VSTR").first()
            if visitor_role:
                ua_vcode = f"UACC-{uuid.uuid4().hex[:8].upper()}"
                new_access = userAccessSchema.UserAccessCreate(
                    vcode=ua_vcode,
                    nid_user=new_user.nid,
                    nid_role=visitor_role.nid,
                    nid_department=admin_access.nid_department,
                    nid_lab=None,
                    vcreated_by=current_user.vcode,
                )
                userAccessController.create_user_access(db=db, user_access=new_access)
                logger.info("Auto-assign VSTR untuk user %s di dept %s", new_user.vemail, admin_access.nid_department)
            else:
                logger.warning("Role VSTR tidak ditemukan, auto-assign gagal.")

        logger.info("User %s berhasil dibuat oleh %s", new_user.vemail, current_user.vemail)
        return new_user

    except ValueError as e:
        logger.warning("Gagal admin-create: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error admin-create: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal membuat pengguna.")


@router.post("/register", response_model=schema.User, status_code=status.HTTP_201_CREATED)
async def register_user_publicly(
    user_data: UserRegister,
    request: Request,
    db: Session = Depends(get_db),
):
    logger.info("Registrasi publik diterima untuk email: %s", user_data.vemail)
    try:
        new_user = await usersController.register_new_user(
            db=db, user_data=user_data, app=request.app, request=request, db_factory=SessionLocal
        )
        logger.info("User %s berhasil dibuat (pending)", new_user.vemail)
        return new_user
    except ValueError as e:
        detail = str(e)
        logger.warning("Registrasi gagal: %s", detail)
        if "sudah terdaftar" in detail or "sudah digunakan" in detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    except Exception as e:
        logger.exception("Unexpected error register: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal mendaftarkan pengguna.")


@router.put("/{user_vcode}", response_model=schema.User)
async def update_existing_user(
    user_vcode: str,
    user_update_data: schema.UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: schema.User = Depends(usersController.get_current_active_user_from_cookie),
):
    logger.info("Update user %s diminta oleh %s", user_vcode, current_user.vemail)
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)

    target_user = usersController.get_user_by_code(db, user_code=user_vcode)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pengguna tidak ditemukan.")

    is_self = current_user.vcode == user_vcode
    is_admin = any(role in ALLOWED_ADMIN_ROLES for role in user_roles)

    if not is_self and not is_admin:
        logger.warning("Forbidden update: %s -> %s", current_user.vemail, user_vcode)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk mengupdate pengguna ini.",
        )

    try:
        user_update_data.vmodified_by = current_user.vcode
        updated_user = await usersController.update_user(
            db=db, user_vcode=user_vcode, user=user_update_data,
            app=request.app, db_factory=SessionLocal, request=request,
        )
        if updated_user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Security log
        log_detail = (
            f"User {current_user.vemail} memperbarui datanya sendiri."
            if is_self
            else f"Admin {current_user.vemail} memperbarui akun {target_user.vemail}."
        )
        auditLogController.create_security_log(
            db=db, nid_user=current_user.nid, action="ACCOUNT_UPDATED",
            request=request, details=log_detail,
        )
        db.commit()
        logger.info("User %s berhasil diupdate oleh %s", user_vcode, current_user.vemail)
        return updated_user

    except ValueError as e:
        logger.warning("Update gagal: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error update: %s", e)
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal mengupdate pengguna.")


@router.delete("/{user_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_user(
    user_vcode: str,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
    current_user: schema.User = Depends(usersController.get_current_active_user_from_cookie),
):
    logger.info("Soft delete user %s oleh %s", user_vcode, current_user.vemail)
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)

    if not any(role in ALLOWED_ADMIN_ROLES for role in user_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk menghapus pengguna.",
        )

    if current_user.vcode == user_vcode:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tidak dapat menghapus akun sendiri.",
        )

    target_user = usersController.get_user_by_code(db, user_code=user_vcode)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pengguna tidak ditemukan.")

    deleted_user = usersController.delete_user(db=db, user_vcode=user_vcode, current_user=current_user.vcode)
    if deleted_user is None or deleted_user.nstatus != 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pengguna tidak ditemukan atau gagal dihapus.")

    try:
        auditLogController.create_security_log(
            db=db, nid_user=current_user.nid, action="ACCOUNT_DEACTIVATED",
            request=request,
            details=f"Admin {current_user.vemail} menonaktifkan akun {target_user.vemail}",
        )
        db.commit()
        logger.info("Soft delete & log berhasil untuk %s", user_vcode)
    except Exception as log_err:
        db.rollback()
        logger.exception("Gagal menyimpan security log delete: %s", log_err)

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
    current_user: schema.User = Depends(usersController.get_current_active_user_from_cookie),
):
    logger.info("GET /users/ oleh %s", current_user.vemail)
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if not any(role in ALLOWED_ADMIN_ROLES for role in user_roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")

    return usersController.get_users(
        db=db, current_user=current_user, skip=skip, limit=limit,
        search=search, nstatus=nstatus, vname=name, vemail=email, vcode=code,
    )


@router.get("/{user_id}", response_model=schema.User)
def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: schema.User = Depends(usersController.get_current_active_user_from_cookie),
):
    logger.info("GET /users/%d oleh %s", user_id, current_user.vemail)
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    is_admin = any(role in ALLOWED_ADMIN_ROLES for role in user_roles)
    if not is_admin and current_user.nid != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")

    user = usersController.get_user(db=db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pengguna tidak ditemukan")
    return user


@router.get("/all-for-dropdown/", response_model=schema.UserDropdownResponse)
def read_all_users_for_dropdown(
    db: Session = Depends(get_db),
    current_user: schema.User = Depends(usersController.get_current_active_user_from_cookie),
):
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if not any(role in ALLOWED_ADMIN_ROLES for role in user_roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
    return usersController.get_all_users_for_dropdown(db=db)


@router.get("/scope-all-for-dropdown/", response_model=schema.UserDropdownResponse)
def read_scope_all_users_for_dropdown(
    db: Session = Depends(get_db),
    current_user: schema.User = Depends(usersController.get_current_active_user_from_cookie),
):
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if not any(role in ALLOWED_ADMIN_ROLES for role in user_roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
    return usersController.get_scoped_users_for_dropdown(db=db, current_user=current_user)


@router.get("/scope-active-for-dropdown/", response_model=schema.UserDropdownResponse)
def read_scope_active_users_for_dropdown(
    db: Session = Depends(get_db),
    current_user: schema.User = Depends(usersController.get_current_active_user_from_cookie),
):
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if not any(role in ALLOWED_ADMIN_ROLES for role in user_roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
    return usersController.get_scoped_active_users_for_dropdown(db=db, current_user=current_user)


@router.get("/all-active-for-dropdown/", response_model=schema.UserDropdownResponse)
def read_all_active_users_for_dropdown(
    db: Session = Depends(get_db),
    current_user: schema.User = Depends(usersController.get_current_active_user_from_cookie),
):
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    if not any(role in ALLOWED_ADMIN_ROLES for role in user_roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
    return usersController.get_all_active_users_for_dropdown(db=db)


# ------------------------------------------------------------------
# ENDPOINT PUBLIK
# ------------------------------------------------------------------

@router.get("/anonymous/{user_vcode}", response_model=schema.UserSafeResponse)
def read_user_anonymous(user_vcode: str, db: Session = Depends(get_db)):
    logger.info("Anonymous lookup: %s", user_vcode)
    user = usersController.get_user_by_code(db, user_code=user_vcode)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pengguna tidak ditemukan")
    return user


@router.post("/set-initial-password", response_model=schema.User)
def set_user_initial_password(
    password_data: schema.SetInitialPassword, request: Request, db: Session = Depends(get_db)
):
    logger.info("Set initial password untuk token: ...%s", password_data.token[-5:])
    try:
        updated = usersController.set_initial_password(db=db, request=request, password_data=password_data)
        logger.info("Password awal berhasil diset untuk %s", updated.vemail)
        return updated
    except ValueError as e:
        detail = str(e)
        logger.warning("Set initial password gagal: %s", detail)
        if any(word in detail for word in ("tidak valid", "kedaluwarsa", "digunakan", "tidak ditemukan")):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    except Exception as e:
        logger.exception("Unexpected error set initial password: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal mengatur password.")


@router.post("/resend-activation/{user_vcode}", status_code=status.HTTP_200_OK)
async def resend_user_activation(user_vcode: str, request: Request, db: Session = Depends(get_db)):
    logger.info("Resend aktivasi: %s", user_vcode)
    try:
        msg = await usersController.resend_activation_email(
            db=db, user_vcode=user_vcode, app=request.app, db_factory=SessionLocal
        )
        return msg
    except ValueError as e:
        detail = str(e)
        logger.warning("Resend gagal: %s", detail)
        status_code_ = status.HTTP_404_NOT_FOUND if "tidak ditemukan" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code_, detail=detail)
    except Exception as e:
        logger.exception("Unexpected error resend: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gagal mengirim ulang email: {str(e)}")


@router.get("/validate-activation-token/{token}")
def validate_activation_token(token: str, db: Session = Depends(get_db)):
    logger.info("Validasi token aktivasi: ...%s", token[-5:])
    result = usersController.verify_activation_token(db=db, token=token)
    if not result["valid"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["reason"])
    return result


@router.get("/verify-email-change/{token}", response_model=schema.User)
def verify_user_email_change(token: str, request: Request, db: Session = Depends(get_db)):
    logger.info("Verifikasi email change: ...%s", token[-5:])
    try:
        updated = usersController.verify_and_update_email(db=db, token=token, request=request)
        logger.info("Email berhasil diganti untuk %s", updated.vemail)
        return updated
    except ValueError as e:
        detail = str(e)
        logger.warning("Verifikasi email gagal: %s", detail)
        if any(word in detail for word in ("tidak valid", "kedaluwarsa", "digunakan", "tidak ditemukan")):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    except Exception as e:
        logger.exception("Unexpected error verify email: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal verifikasi email.")


# ------------------------------------------------------------------
# LOGOUT – FIX: tanpa domain agar tidak mismatch
# ------------------------------------------------------------------
@router.post("/logout")
async def logout(
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(usersController.get_current_active_user_from_cookie),
):
    logger.info("Logout request dari %s", current_user.vemail)
    
    # Audit log
    try:
        auditLogController.create_security_log(
            db=db, nid_user=current_user.nid, action="LOGOUT", request=request
        )
        # Jangan commit dulu, gabung dengan transaksi nonaktifkan token
    except Exception as e:
        logger.exception("Gagal simpan log logout: %s", e)
        db.rollback()
        # Meskipun gagal log, tetap lanjutkan logout (jangan return error)

    # Ambil refresh_token dari cookie untuk menandai session yang akan diakhiri
    refresh_token_cookie = request.cookies.get("refresh_token")
    
    try:
        # Nonaktifkan semua token session (type 2) milik user ini yang masih aktif
        db.query(Token).filter(
            Token.nid_user == current_user.nid,
            Token.ntoken_type == 2,
            Token.nstatus == 1
        ).update(
            {"nstatus": 0, "dmodified_at": to_wib(datetime.now(JAKARTA_TZ))},
            synchronize_session=False
        )
        # Jika ingin lebih spesifik: hanya nonaktifkan token yang cocok dengan refresh_token,
        # tapi akan lebih aman matikan semua session user yang aktif.
        
        db.commit()
        logger.info("Token session dinonaktifkan untuk user %s", current_user.vemail)
    except Exception as e:
        db.rollback()
        logger.exception("Gagal nonaktifkan token: %s", e)
        # Jika gagal, tetap hapus cookie agar user logout di sisi browser

    # Hapus cookie dengan DOMAIN YANG SAMA seperti saat set_cookie
    # Gunakan COOKIE_DOMAIN (None jika tidak ada env) untuk konsistensi
    response.delete_cookie(
        "access_token",
        path="/",
        domain=COOKIE_DOMAIN,          # <-- penting
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE
    )
    response.delete_cookie(
        "refresh_token",
        path="/users/refresh_token",
        domain=COOKIE_DOMAIN,          # <-- penting
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE
    )

    logger.info("Cookie auth dihapus untuk user %s", current_user.vemail)
    return {"message": "Logout successful"}

@router.post("/activate-account", response_model=schema.User)
def activate_newly_registered_user(
    token_data: ActivationToken, request: Request, db: Session = Depends(get_db)
):
    logger.info("Aktivasi akun baru: ...%s", token_data.token[-5:])
    try:
        activated = usersController.activate_registered_user(db=db, request=request, token=token_data.token)
        logger.info("Akun berhasil diaktivasi: %s", activated.vemail)
        return activated
    except ValueError as e:
        detail = str(e)
        logger.warning("Aktivasi gagal: %s", detail)
        if any(word in detail for word in ("tidak valid", "kedaluwarsa", "digunakan", "tidak ditemukan")):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        if "sudah aktif" in detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    except Exception as e:
        logger.exception("Unexpected error aktivasi: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal mengaktifkan akun.")


@router.post("/request-password-reset", status_code=status.HTTP_200_OK)
async def request_password_reset_endpoint(
    request_data: RequestPasswordReset, request: Request, db: Session = Depends(get_db)
):
    logger.info("Request password reset: %s", request_data.email)
    try:
        msg = await usersController.request_password_reset(
            db=db, email=request_data.email, request=request, app=request.app, db_factory=SessionLocal
        )
        return msg
    except Exception as e:
        logger.exception("Unexpected error request reset: %s", e)
        # Selalu kembalikan pesan generik untuk alasan keamanan
        return {"message": "Jika email Anda terdaftar, instruksi reset password akan dikirim."}


@router.get("/validate-reset-token/{token}")
def validate_reset_token(token: str, db: Session = Depends(get_db)):
    logger.info("Validasi token reset: ...%s", token[-5:])
    result = usersController.verify_reset_token(db=db, token=token)
    if not result["valid"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["reason"])
    return result


@router.post("/reset-password", response_model=schema.User)
def reset_user_password(password_data: ResetPassword, request: Request, db: Session = Depends(get_db)):
    logger.info("Reset password: ...%s", password_data.token[-5:])
    try:
        updated = usersController.reset_password(db=db, password_data=password_data, request=request)
        logger.info("Password berhasil direset untuk %s", updated.vemail)
        return updated
    except ValueError as e:
        detail = str(e)
        logger.warning("Reset password gagal: %s", detail)
        if any(word in detail for word in ("tidak valid", "kedaluwarsa", "digunakan", "tidak ditemukan")):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    except Exception as e:
        logger.exception("Unexpected error reset password: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal mengatur password baru.")