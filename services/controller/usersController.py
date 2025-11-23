import os
import secrets
from datetime import datetime, timedelta
import uuid
import pytz
import threading
import sys
import time

from fastapi import Depends, HTTPException, status, Request, Response # Ditambah Response
from fastapi_apscheduler import scheduler
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
from jose import JWTError, jwt # type: ignore
# OAuth2PasswordBearer gak dipake lagi buat get user, tapi mungkin masih perlu kalo ada endpoint lain yg pake
# from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import aliased
from ..models import usersModel as models
from ..models import tokenModel
from ..schemas import usersSchema as schema
from utils.email_service import send_activation_email, send_email_change_verification_email, send_password_reset_email
# Import util refresh token
from utils.token_refresh import refresh_access_cookie, RefreshConfig
from ..database import SessionLocal
from . import auditLogController
from ..models import rolesModel, userAccessModel
from ..schemas.usersSchema import UserRegister

jakarta_tz = pytz.timezone("Asia/Jakarta")

def now_wib():
    return datetime.now(jakarta_tz)


# --- HELPERS ---

def to_wib(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        return jakarta_tz.localize(dt)
    return dt.astimezone(jakarta_tz)

PASSWORD_PEPPER = os.getenv("PASSWORD_PEPPER")
if not PASSWORD_PEPPER:
    raise ValueError("CRITICAL: PASSWORD_PEPPER not found in environment variables.")

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
# Durasi token/cookie (dalam menit/hari, akan diubah ke detik di API)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1")) # Default 15 menit
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30")) # Default 30 hari

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/token") # Gak dipake lagi buat get_current_user via cookie


# --- Config & Wrapper untuk Refresh Token ---

class _AuthControllerWrapper:
    """
    Wrapper internal untuk meneruskan fungsi refresh_access_token 
    (dari file ini) ke util refresh_access_cookie.
    """
    @staticmethod
    async def refresh_access_token(db: Session, refresh_token: str) -> tuple[str, int]:
        # Panggil fungsi 'refresh_access_token' yang didefinisikan di file ini
        return await refresh_access_token(db=db, refresh_token=refresh_token)

auth_controller_wrapper = _AuthControllerWrapper()

# Konfigurasi untuk util refresh_access_cookie
refresh_cfg = RefreshConfig(
    access_cookie_key="access_token",
    refresh_cookie_key="refresh_token",
    access_cookie_path="/",
    refresh_cookie_path="/users/refresh_token", # Pastikan sesuai dengan endpoint refresh di API
    cookie_secure=os.getenv("COOKIE_SECURE", "True").lower() == "true",
    cookie_samesite=os.getenv("COOKIE_SAMESITE", "lax"),
    access_cookie_max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60 # Konversi menit ke detik
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Fungsi Pembuatan Token ---
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = now_wib() + expires_delta
    else:
        expire = now_wib() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    print(f"Creating access token with expiration at {expire.isoformat()}")
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = now_wib() + expires_delta
    else:
        # Ubah ke days sesuai variabel baru
        expire = now_wib() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    # Optionally add a claim to distinguish refresh tokens if needed, e.g., to_encode["type"] = "refresh"
    print(f"Creating refresh token with expiration at {expire.isoformat()}")
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- Fungsi Autentikasi User ---
def authenticate_user(
    db: Session, 
    email: str, 
    password: str, 
    request: Request # <-- TAMBAH INI
) -> models.User | None:
    
    user = get_user_by_email(db, email=email)

    if not user:
        print(f"Login attempt failed: Email '{email}' not found.")
        # --- LOG GAGAL ---
        auditLogController.create_security_log(
            db=db, nid_user=None, action="LOGIN_FAILED", 
            request=request, details=f"Attempted email: {email}, reason: user not found"
        )
        db.commit()
        # -------------------
        return None

    if user.nstatus == 0:
        print(f"Login attempt failed: User '{email}' is inactive.")
        # --- LOG GAGAL ---
        auditLogController.create_security_log(
            db=db, nid_user=user.nid, action="LOGIN_FAILED", 
            request=request, details="Reason: inactive user for user '{email}'"
        )
        db.commit()
        # -------------------
        raise ValueError("Akun Anda tidak aktif.")
        
    if user.nstatus == 2:
        print(f"Login attempt failed: User '{email}' is pending activation.")
        # --- LOG GAGAL ---
        auditLogController.create_security_log(
            db=db, nid_user=user.nid, action="LOGIN_FAILED", 
            request=request, details="Reason: pending activation for user '{email}'"
        )
        db.commit()
        # -------------------
        raise ValueError("Akun Anda belum diaktivasi. Silakan cek email Anda.")
        
    if user.nstatus == 3:
        print(f"Login attempt failed: User '{email}' activation expired.")
        # --- LOG GAGAL ---
        auditLogController.create_security_log(
            db=db, nid_user=user.nid, action="LOGIN_FAILED", 
            request=request, details="Reason: activation expired for user '{email}'"
        )
        db.commit()
        # -------------------
        raise ValueError("Aktivasi akun Anda sudah kedaluwarsa. Silakan minta kirim ulang email aktivasi.")
        
    if not user.vpassword:
         print(f"Login attempt failed: User '{email}' has no password set (likely created by admin).")
         # --- LOG GAGAL ---
         auditLogController.create_security_log(
            db=db, nid_user=user.nid, action="LOGIN_FAILED", 
            request=request, details="Reason: password not set for user '{email}'"
         )
         db.commit()
         # -------------------
         raise ValueError("Password belum diatur. Silakan gunakan link aktivasi di email Anda.")

    if user.nstatus == 1 and user.vpassword:
        if not verify_password(password, user.vpassword):
            print(f"Login attempt failed: Invalid password for user '{email}'.")
            # --- LOG GAGAL ---
            auditLogController.create_security_log(
                db=db, nid_user=user.nid, action="LOGIN_FAILED", 
                request=request, details="Reason: invalid password for user '{email}'"
            )
            db.commit()
            # -------------------
            return None
    else:
        # Kondisi ini seharusnya tidak terjadi jika nstatus=1, tapi jaga-jaga
        print(f"Login attempt failed: User '{email}' has invalid status ({user.nstatus}) or no password for verification.")
        # --- LOG GAGAL ---
        auditLogController.create_security_log(
            db=db, nid_user=user.nid, action="LOGIN_FAILED", 
            request=request, details=f"Reason: invalid state (status {user.nstatus})"
        )
        db.commit()
        # -------------------
        return None

    print(f"Login attempt successful for user '{email}'.")
    # --- LOG SUKSES ---
    auditLogController.create_security_log(
        db=db, nid_user=user.nid, action="LOGIN_SUCCESS", request=request
    )
    # ------------------
    return user

# --- Fungsi Refresh Token (Diubah) ---
# Hanya menerima db dan refresh_token string, return tuple (new_access_token, user_nid)
async def refresh_access_token(db: Session, refresh_token: str) -> tuple[str, int]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        # headers={"WWW-Authenticate": "Bearer"}, # Header gak relevan
    )
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        user_nid = int(user_id)
    except (JWTError, ValueError):
        raise credentials_exception

    user = get_user(db, user_id=user_nid)
    # Penting: Cek user ada dan aktif!
    if user is None or user.nstatus != 1:
        raise credentials_exception

    # Create a new access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_access_token(
        data={"sub": str(user.nid)}, expires_delta=access_token_expires
    )
    return new_access_token, user.nid # Kembalikan tuple

# --- Fungsi Get Current User (Baru, dari Cookie) ---
async def get_current_user_from_cookie(request: Request, db: Session = Depends(get_db)):
    """
    Versi standar: Coba dapatkan user dari access_token.
    Jika token expired atau tidak valid, fungsi ini akan GAGAL (raise 401).
    Fungsi ini tetap ada jika diperlukan dependency yang tidak auto-refresh.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials from cookie",
        # headers={"WWW-Authenticate": "Bearer"}, # Header gak relevan
    )
    token = request.cookies.get("access_token") # <-- Baca dari cookie 'access_token'
    if token is None:
        print("Get current user failed: Access token cookie not found.")
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            print("Get current user failed: User ID (sub) not found in token payload.")
            raise credentials_exception
        user_nid = int(user_id)
    except (JWTError, ValueError) as e:
        print(f"Get current user failed: Token decode error or invalid User ID. Error: {e}")
        # Di sini bisa ditambahkan logika coba refresh token jika access token expired
        # Tapi untuk simpelnya, kita raise error dulu
        raise credentials_exception # <-- Langsung error kalo gak valid/expired

    user = get_user(db, user_id=user_nid)
    if user is None:
        print(f"Get current user failed: User with NID {user_nid} not found in database.")
        raise credentials_exception

    print(f"Get current user successful: User NID {user.nid}, Email {user.vemail}")
    return user

# --- Fungsi Get Current Active User (Baru, dari Cookie) ---
# === FUNGSI YANG DIMODIFIKASI ===
async def get_current_active_user_from_cookie(
    request: Request, 
    response: Response, 
    db: Session = Depends(get_db)
):
    """
    Dependency baru: Coba dapatkan user dari access_token.
    Jika access_token tidak ada atau expired, otomatis coba refresh
    menggunakan refresh_token. Jika berhasil, set cookie baru dan 
    lanjutkan. Jika gagal (refresh token juga invalid), baru raise 401.
    Setelah user didapat, cek nstatus == 1.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials from cookie (active check)",
    )
    token = request.cookies.get(refresh_cfg.access_cookie_key) # Gunakan cfg
    
    user_nid = None # Inisialisasi user_nid
    
    if token is None:
        print("Get current active user failed: Access token cookie not found.")
        print("Attempting token refresh because access token is missing...")
        try:
            # Coba refresh
            refresh_result = await refresh_access_cookie(
                request=request,
                response=response,
                db=db,
                users_controller=auth_controller_wrapper, # Pakai wrapper
                cfg=refresh_cfg
            )
            # Jika sukses, token baru sudah di-set di cookie.
            # Ambil token baru dari hasil refresh untuk di-decode
            token = refresh_result.get("access_token") 
            if not token: # Safety check
                raise credentials_exception
            print("Refresh successful (after missing token). Proceeding with new token.")
        
        except HTTPException as refresh_exc:
            print(f"Refresh failed (after missing token): {refresh_exc.detail}")
            # Re-raise dengan detail yang lebih spesifik
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Sesi tidak valid atau sudah berakhir. (Refresh Failed: {refresh_exc.detail})",
            )

    # (Lanjut ke try-decode)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            print("Get current active user failed: User ID (sub) not found in token payload.")
            raise credentials_exception
        user_nid = int(user_id)
    
    except JWTError as e: # Tangkap JWTError spesifik
        error_msg = str(e).lower()
        print(f"Get current active user failed: Token decode error. Error: {error_msg}")
        
        # Cek apakah error karena expired
        if "expired" in error_msg:
            print("Access token expired. Attempting token refresh...")
            try:
                # Panggil refresh_access_cookie
                refresh_result = await refresh_access_cookie(
                    request=request,
                    response=response,
                    db=db,
                    users_controller=auth_controller_wrapper, # Pakai wrapper
                    cfg=refresh_cfg
                )
                # Jika sukses, token baru ada di response cookie.
                # Kita decode token *baru* ini
                new_token = refresh_result.get("access_token")
                if not new_token: # Safety check
                    raise credentials_exception
                    
                payload = jwt.decode(new_token, SECRET_KEY, algorithms=[ALGORITHM])
                user_id: str | None = payload.get("sub")
                if user_id is None:
                     print("Get current active user failed: User ID (sub) not found in *refreshed* token.")
                     raise credentials_exception
                user_nid = int(user_id)
                print("Refresh successful. Proceeding with new token.")

            except HTTPException as refresh_exc:
                print(f"Refresh failed (after token expired): {refresh_exc.detail}")
                # Re-raise dengan detail yang lebih spesifik
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Sesi Anda telah berakhir dan gagal diperbarui. ({refresh_exc.detail})",
                )
            except (JWTError, ValueError) as decode_e: # Error pas decode token baru (aneh)
                print(f"Get current active user failed: Error decoding *refreshed* token. Error: {decode_e}")
                raise credentials_exception
        
        else: # JWTError tapi bukan expired (misal signature invalid)
            print("Token invalid (not expired). Raising 401.")
            raise credentials_exception
    
    except ValueError as e: # Gagal int(user_id)
         print(f"Get current active user failed: Invalid User ID (ValueError). Error: {e}")
         raise credentials_exception
    
    # --- (Validasi User) ---
    if user_nid is None: # Safety check jika logic di atas gagal
         print("Get current active user failed: User NID not determined.")
         raise credentials_exception

    user = get_user(db, user_id=user_nid)
    if user is None:
        # Jika user tidak ditemukan di DB (misal dihapus), hapus cookie
        print(f"Get current active user failed: User with NID {user_nid} not found in database. Deleting cookies.")
        response.delete_cookie(
            refresh_cfg.refresh_cookie_key,
            path=refresh_cfg.refresh_cookie_path,
            secure=refresh_cfg.cookie_secure,
            samesite=refresh_cfg.cookie_samesite,
        )
        response.delete_cookie(
            refresh_cfg.access_cookie_key,
            path=refresh_cfg.access_cookie_path,
            secure=refresh_cfg.cookie_secure,
            samesite=refresh_cfg.cookie_samesite,
        )
        raise credentials_exception

    # --- (Validasi Status Aktif - dari fungsi asli) ---
    if user.nstatus != 1:
        print(f"Get current active user failed: User NID {user.nid} is inactive (status: {user.nstatus}).")
        raise HTTPException(status_code=400, detail="Inactive user") 
    
    print(f"Get current active user successful: User NID {user.nid}, Email {user.vemail}")
    return user


# --- Fungsi CRUD dan Operasi User Lainnya (umumny hanya dependency auth yg berubah di API layer) ---

async def create_user_by_admin(db: Session, user_data: schema.UserCreateByAdmin, request: Request, app=None, db_factory=None):
    # Logika fungsi ini tidak berubah
    db_user = models.User(**user_data.model_dump(), vpassword=None, nstatus=2)
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        activation_token_str = secrets.token_urlsafe(32)
        expires_at = now_wib() + timedelta(hours=24) # Aktivasi 24 jam

        db_token = tokenModel.Token(
            nid_user=db_user.nid,
            ntoken_type=1, # Tipe 1 = Aktivasi
            vcode=activation_token_str,
            dexpires_at=expires_at,
            nstatus=1 # Status 1 = Aktif
        )
        db.add(db_token)
        db.commit()
        db.refresh(db_token)
        
        admin_user = get_user_by_code(db, user_code=user_data.vcreated_by)
        admin_nid = admin_user.nid if admin_user else None
        
        auditLogController.create_security_log(
            db=db, 
            nid_user=admin_nid, # User yg login (admin)
            action="ACCOUNT_CREATED_BY_ADMIN", 
            request=request, 
            details=f"New user created: {db_user.vemail} (NID: {db_user.nid})"
        )
        db.commit()

        try:
            await send_activation_email(
                recipient_email=db_user.vemail,
                user_name=db_user.vname,
                activation_token=activation_token_str,
            )
        except Exception as e:
            # Tetap lanjutkan walau email gagal, tapi log errornya
            print(f"ERROR: User {db_user.vemail} created, BUT failed to send activation email. Error: {e}")
            # Mungkin tambahkan flag di user atau log terpisah untuk follow up manual

        # Jadwalkan expiry token jika scheduler ada
        if app and hasattr(app.state, "scheduler") and db_factory:
            schedule_token_expiry(
                sched=app.state.scheduler,
                db_factory=db_factory,
                user_id=db_user.nid,
                token_id=db_token.nid,
                task_type='user_activation',
                delay_seconds=24 * 60 * 60 # 24 jam dalam detik
            )

        print(f"✅ User {db_user.vemail} created, activation email sent (or attempted), expiry in 24h.")
        return db_user

    except IntegrityError as e:
        db.rollback()
        error_info = str(e.orig).lower()
        print(f"IntegrityError during user creation: {error_info}")
        # Cek error spesifik (misal email/vcode duplikat)
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
             if 'vemail' in error_info:
                 raise ValueError("Gagal menyimpan. Email sudah digunakan.")
             elif 'vcode' in error_info:
                 raise ValueError("Gagal menyimpan. NIM/NIK sudah digunakan.")
             else:
                 raise ValueError("Gagal menyimpan. Data unik sudah ada.")
        else:
            raise ValueError("Gagal menyimpan pengguna baru.")

async def register_new_user(db: Session, user_data: UserRegister,request: Request, app=None, db_factory=None):
    """
    Membuat user baru dari registrasi publik (status Pending).
    """
    # 1. Validasi Duplikat
    if get_user_by_email(db, email=user_data.vemail):
        raise ValueError("Email ini sudah terdaftar. Silakan gunakan email lain.")
    if get_user_by_code(db, user_code=user_data.vcode):
        raise ValueError("NIM/NIK ini sudah terdaftar. Silakan hubungi admin jika ada kesalahan.")

    # 2. Cari Role VSTR (Visitor)
    vstr_role = db.query(rolesModel.Role).filter(rolesModel.Role.vcode == 'VSTR').first()
    if not vstr_role:
        print("CRITICAL: Role 'VSTR' tidak ditemukan di database. Registrasi publik gagal.")
        raise ValueError("Sistem registrasi sedang tidak tersedia. (Error: R_VSTR_NF)")

    # 3. Hash Password
    hashed_password = get_password_hash(user_data.password)

    try:
        # 4. Buat User baru (status 2 = Pending)
        db_user = models.User(
            vcode=user_data.vcode,
            vname=user_data.vname,
            vemail=user_data.vemail,
            vphone=user_data.vphone,
            vaddress=user_data.vaddress,
            vpassword=hashed_password, # Langsung simpan password yg di-hash
            nstatus=2, # Status Pending menunggu aktivasi
            vcreated_by="system-register"
        )
        db.add(db_user)
        db.flush() # Penting: Dapatkan NID user baru (db_user.nid) sebelum commit

        # 5. Buat UserAccess (langsung assign role VSTR & Department)
        db_user_access = userAccessModel.UserAccess(
            vcode=str(uuid.uuid4()),
            nid_user=db_user.nid,
            nid_role=vstr_role.nid,
            nid_department=user_data.nid_department,
            nstatus=1, # Bikin langsung aktif
            vcreated_by="system-register"
        )
        db.add(db_user_access)

        # 6. Buat Token Aktivasi (Tipe 1)
        activation_token_str = secrets.token_urlsafe(32)
        expires_at = now_wib() + timedelta(hours=24) # Aktivasi 24 jam

        db_token = tokenModel.Token(
            nid_user=db_user.nid,
            ntoken_type=1, # Tipe 1 = Aktivasi
            vcode=activation_token_str,
            dexpires_at=expires_at,
            nstatus=1 # Status 1 = Aktif
        )
        db.add(db_token)
        
        # Commit semua perubahan (User, UserAccess, Token)
        db.commit()
        
        db.refresh(db_user)
        db.refresh(db_token)
        
        auditLogController.create_security_log(
            db=db, nid_user=db_user.nid, action="ACCOUNT_REGISTER_SUCCESS", 
            request=request, details="Account created, pending activation."
        )
        db.commit()

    except IntegrityError as e:
        db.rollback()
        error_info = str(e.orig).lower()
        print(f"IntegrityError during public registration: {error_info}")
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
             if 'vemail' in error_info:
                 raise ValueError("Gagal menyimpan. Email sudah digunakan.")
             elif 'vcode' in error_info:
                 raise ValueError("Gagal menyimpan. NIM/NIK sudah digunakan.")
        else:
             raise ValueError("Gagal menyimpan pengguna baru.")
    except Exception as e:
        db.rollback()
        print(f"Unexpected error during public registration: {e}")
        raise ValueError("Terjadi kesalahan internal saat mendaftar.")

    # 7. Kirim Email (Diluar Try/Catch DB)
    try:
        await send_activation_email(
            recipient_email=db_user.vemail,
            user_name=db_user.vname,
            activation_token=activation_token_str,
            path="/auth/activate-account/"
        )
    except Exception as e:
        # Email gagal, tapi user udah dibuat. User bisa minta resend.
        print(f"ERROR: User {db_user.vemail} registered, BUT failed to send activation email. Error: {e}")

    # 8. Jadwalkan Expiry Token
    if app and hasattr(app.state, "scheduler") and db_factory:
        schedule_token_expiry(
            sched=app.state.scheduler,
            db_factory=db_factory,
            user_id=db_user.nid,
            token_id=db_token.nid,
            task_type='user_activation',
            delay_seconds=24 * 60 * 60 # 24 jam
        )

    print(f"✅ User {db_user.vemail} registered (Pending), activation email sent.")
    
    # Kembalikan data user yang baru dibuat (tanpa password)
    return db_user


async def update_user(db: Session, user_vcode: str, user: schema.UserUpdate, request: Request, app=None, db_factory=None):
    # Logika fungsi ini tidak berubah, termasuk pengiriman email verifikasi
    db_user = get_user_by_code(db, user_code=user_vcode)
    if not db_user:
        return None

    db_user.vmodified_by = user.vmodified_by or 'system' # Default ke system kalo kosong
    update_data = user.model_dump(exclude_unset=True) # Hanya ambil field yg di-set

    # --- Penanganan Perubahan Email ---
    if 'vemail' in update_data and update_data['vemail'] != db_user.vemail:
        new_email = update_data.pop('vemail') # Ambil dan hapus dari update_data
        print(f"Email change initiated for user {db_user.vcode}. New email: {new_email}")

        # Cek dulu apakah email baru sudah dipakai user lain
        existing_user_check = get_user_by_email(db, email=new_email)
        if existing_user_check and existing_user_check.nid != db_user.nid:
             print(f"Email change failed: New email '{new_email}' already used by user NID {existing_user_check.nid}.")
             raise ValueError("Gagal memulai perubahan email. Email baru sudah digunakan oleh pengguna lain.")

        verification_token_str = secrets.token_urlsafe(32)
        expires_at = now_wib() + timedelta(hours=24) # Verifikasi 24 jam

        # Buat token verifikasi email baru (Tipe 4)
        db_token = tokenModel.Token(
            nid_user=db_user.nid,
            ntoken_type=4, # Tipe 4 = Ganti Email
            vcode=verification_token_str,
            vnew_email=new_email, # Simpan email baru di token
            dexpires_at=expires_at,
            nstatus=1 # Status 1 = Aktif
        )
        db.add(db_token)

        try:
            db.commit() # Commit token dulu
            db.refresh(db_token)
            auditLogController.create_security_log(
                db=db, nid_user=db_user.nid, action="EMAIL_CHANGE_REQUEST", 
                request=request, details=f"New email requested: {new_email}"
            )
            db.commit()
        except IntegrityError: # Jarang terjadi, tapi jaga-jaga kalo token vcode duplikat
            db.rollback()
            print(f"Email change failed: Could not save verification token for {new_email}.")
            raise ValueError("Gagal memulai perubahan email. Silakan coba lagi.")

        # Kirim email verifikasi ke email BARU
        try:
             await send_email_change_verification_email(
                 recipient_email=new_email, # Kirim ke email baru
                 user_name=db_user.vname,
                 verification_token=verification_token_str,
             )
        except Exception as e:
             # Email gagal, tapi token udah dibuat. Log errornya.
             print(f"ERROR: Verification token for email change to {new_email} created, BUT failed to send email. Error: {e}")
             # User harus coba update lagi atau kontak admin

        # Jadwalkan expiry token
        if app and hasattr(app.state, "scheduler") and db_factory:
            schedule_token_expiry(
                sched=app.state.scheduler,
                db_factory=db_factory,
                user_id=db_user.nid,
                token_id=db_token.nid,
                task_type='email_change',
                delay_seconds=24*60*60 # 24 jam
            )

        print(f"📧 Verification email sent to {new_email} for user {db_user.vcode}. Expires in 24 hours.")
        # Jangan update email user di sini, tunggu verifikasi

    # Update field user lainnya (selain email jika sedang diverifikasi)
    for key, value in update_data.items():
        if hasattr(db_user, key):
            setattr(db_user, key, value)
        else:
             print(f"Warning: Trying to update non-existent attribute '{key}' for user {db_user.vcode}")


    try:
        db_user.dsort_at = now_wib() # Update timestamp sortir
        db.commit()
        db.refresh(db_user)
        print(f"✅ User {db_user.vcode} updated successfully (Email change might be pending verification).")
        return db_user
    except IntegrityError as e: # Handle kalo ada constraint lain yg violate (misal vcode duplikat)
        db.rollback()
        error_info = str(e.orig).lower()
        print(f"IntegrityError during user update: {error_info}")
        if 'unique constraint' in error_info or 'duplicate entry' in error_info:
             if 'vcode' in error_info: # Misal kalo vcode juga diupdate dan duplikat
                 raise ValueError("Gagal memperbarui pengguna. NIM/NIK yang baru sudah digunakan.")
             else: # Constraint unik lainnya
                  raise ValueError("Gagal memperbarui pengguna. Data unik sudah ada.")
        else:
            raise ValueError("Gagal memperbarui pengguna.")


async def resend_activation_email(db: Session, user_vcode: str, app=None, db_factory=None):
    # Logika fungsi ini tidak berubah
    user = get_user_by_code(db, user_code=user_vcode)
    if not user:
        raise ValueError("Pengguna tidak ditemukan.")
    # Hanya bisa resend kalo status Pending (2) atau Expired (3)
    if user.nstatus not in [2, 3]:
        status_map = {0: "Tidak Aktif", 1: "Aktif"}
        current_status = status_map.get(user.nstatus, f"Status {user.nstatus}")
        raise ValueError(f"Pengguna sudah {current_status}, tidak bisa mengirim ulang aktivasi.")

    # Buat token aktivasi baru
    activation_token_str = secrets.token_urlsafe(32)
    expires_at = now_wib() + timedelta(hours=24) # 24 jam lagi

    # Nonaktifkan token lama (jika ada yg masih aktif) - Opsional tapi bagus
    db.query(tokenModel.Token).filter(
        tokenModel.Token.nid_user == user.nid,
        tokenModel.Token.ntoken_type == 1, # Tipe Aktivasi
        tokenModel.Token.nstatus == 1 # Yang masih aktif
    ).update({"nstatus": 0})
    # Kita commit ini bareng token baru

    db_token = tokenModel.Token(
        nid_user=user.nid,
        ntoken_type=1, # Tipe Aktivasi
        vcode=activation_token_str,
        dexpires_at=expires_at,
        nstatus=1 # Aktif
    )
    db.add(db_token)

    # Kalo status user Expired (3), ubah jadi Pending (2) lagi
    if user.nstatus == 3:
        user.nstatus = 2
        user.vmodified_by = "system-resend" # Tandai pengubah
        user.dsort_at = now_wib()

    try:
        db.commit() # Commit user status change & token baru & penonaktifan token lama
        db.refresh(db_token) # Refresh token baru buat dapet ID
    except Exception as commit_error:
        db.rollback()
        print(f"Error committing resend activation changes for {user.vemail}: {commit_error}")
        raise ValueError("Gagal memproses pengiriman ulang email aktivasi.")


    # Kirim email
    try:
        await send_activation_email(
            recipient_email=user.vemail,
            user_name=user.vname,
            activation_token=activation_token_str,
        )
    except Exception as e:
        # Email gagal, tapi token udah dibuat & user status udah diupdate. Log errornya.
        print(f"ERROR: Resend activation for {user.vemail} processed, BUT failed to send email. Error: {e}")
        # Mungkin perlu mekanisme notifikasi admin atau retry

    # Jadwalkan expiry token baru
    if app and hasattr(app.state, "scheduler") and db_factory:
        schedule_token_expiry(
            sched=app.state.scheduler,
            db_factory=db_factory,
            user_id=user.nid,
            token_id=db_token.nid, # Token ID yg baru
            task_type='user_activation',
            delay_seconds=24 * 60 * 60 # 24 jam
        )

    print(f"🔁 Resent activation email to {user.vemail}, expiry in 24 hours.")
    return {"message": "Email aktivasi telah berhasil dikirim ulang."}


def set_initial_password(db: Session, password_data: schema.SetInitialPassword, request: Request):
    # Logika fungsi ini tidak berubah
    # Cari token aktivasi (tipe 1)
    db_token = db.query(tokenModel.Token).filter(
        tokenModel.Token.vcode == password_data.token,
        tokenModel.Token.ntoken_type == 1 # Pastikan tipe aktivasi
    ).first()

    if not db_token:
        raise ValueError("Token aktivasi tidak valid atau tidak ditemukan.")
    if db_token.nstatus == 0:
        raise ValueError("Tautan aktivasi ini sudah pernah digunakan.")

    # Cek expired
    expires_at_aware = to_wib(db_token.dexpires_at)
    if expires_at_aware < now_wib():
        # Token expired, update status user jadi Expired (3) jika masih Pending (2)
        user_to_update = db.query(models.User).filter(models.User.nid == db_token.nid_user).first()
        if user_to_update and user_to_update.nstatus == 2:
            user_to_update.nstatus = 3
            user_to_update.vmodified_by = "system-token-expired"
            user_to_update.dsort_at = now_wib()
            # Nonaktifkan token juga
            db_token.nstatus = 0
            try:
                db.commit()
            except Exception as commit_error:
                 db.rollback()
                 print(f"Error updating user status on expired token for user NID {db_token.nid_user}: {commit_error}")
                 # Lanjutkan raise error expired, tapi log error internalnya
        elif db_token.nstatus == 1: # Jika token belum dinonaktifkan tapi user status bukan 2
            db_token.nstatus = 0
            try:
                db.commit()
            except Exception:
                db.rollback()
                # Abaikan error commit di sini, fokus ke error expired
        raise ValueError("Tautan aktivasi sudah kedaluwarsa. Silakan minta kirim ulang.")

    # Cari user terkait
    user = db.query(models.User).filter(models.User.nid == db_token.nid_user).first()
    if not user:
        # Harusnya jarang terjadi kalo token ada, tapi jaga-jaga
        db_token.nstatus = 0 # Nonaktifkan token aneh ini
        db.commit()
        raise ValueError("Pengguna yang terkait dengan token ini tidak ditemukan.")

    # Hanya bisa set password awal kalo status user Pending (2)
    if user.nstatus != 2:
        db_token.nstatus = 0 # Nonaktifkan token yg gak relevan ini
        db.commit()
        status_map = {0: "Tidak Aktif", 1: "Aktif", 3: "Kedaluwarsa"}
        current_status = status_map.get(user.nstatus, f"Status {user.nstatus}")
        raise ValueError(f"Tautan aktivasi ini tidak dapat digunakan karena status akun adalah '{current_status}'.")


    # Set password dan aktifkan user
    user.vpassword = get_password_hash(password_data.password)
    user.nstatus = 1 # Jadi Aktif
    user.vmodified_by = "system-activation"
    user.dsort_at = now_wib()
    # Nonaktifkan token setelah dipakai
    db_token.nstatus = 0

    try:
        db.commit()
        db.refresh(user)
        
        auditLogController.create_security_log(
            db=db, nid_user=user.nid, action="ACCOUNT_ACTIVATION_SUCCESS", 
            request=request, details="Initial password set"
        )
        db.commit()   
    except Exception as commit_error:
        db.rollback()
        print(f"Error activating user {user.vemail}: {commit_error}")
        raise ValueError("Gagal mengaktifkan akun. Silakan coba lagi.")


    print(f"✅ Password for user {user.vemail} (ID: {user.nid}) has been successfully set.")
    print(f"   -> User status is now ACTIVE. Any running expiration countdown for this user is now void and will be skipped.")

    return user

def activate_registered_user(db: Session, token: str, request: Request):
    """
    Mengaktifkan user yang mendaftar via publik.
    Hanya memvalidasi token dan mengubah status dari 2 (Pending) ke 1 (Active).
    """
    # 1. Cari token aktivasi (tipe 1)
    db_token = db.query(tokenModel.Token).filter(
        tokenModel.Token.vcode == token,
        tokenModel.Token.ntoken_type == 1 # Pastikan tipe aktivasi
    ).first()

    # 2. Validasi Token
    if not db_token:
        raise ValueError("Token aktivasi tidak valid atau tidak ditemukan.")
    if db_token.nstatus == 0:
        raise ValueError("Tautan aktivasi ini sudah pernah digunakan.")

    # 3. Cek Expired
    expires_at_aware = to_wib(db_token.dexpires_at)
    if expires_at_aware < now_wib():
        # (Logika auto-expire user nstatus 2 -> 3 udah di-handle scheduler, 
        # tapi kita cek lagi di sini buat jaga-jaga)
        user_check = db.query(models.User).filter(models.User.nid == db_token.nid_user, models.User.nstatus == 2).first()
        if user_check:
            user_check.nstatus = 3 # Set Expired
            user_check.vmodified_by = "system-token-expired"
        db_token.nstatus = 0 # Nonaktifkan token
        db.commit()
        raise ValueError("Tautan aktivasi sudah kedaluwarsa. Silakan minta kirim ulang.")

    # 4. Cari User terkait
    user = db.query(models.User).filter(models.User.nid == db_token.nid_user).first()
    if not user:
        db_token.nstatus = 0 
        db.commit()
        raise ValueError("Pengguna yang terkait dengan token ini tidak ditemukan.")

    # 5. Validasi Status User
    if user.nstatus == 1:
        db_token.nstatus = 0 # Nonaktifkan token yg gak relevan ini
        db.commit()
        raise ValueError("Akun ini sudah aktif.")
    if user.nstatus == 3:
        raise ValueError("Aktivasi akun ini sudah kedaluwarsa. Silakan minta kirim ulang.")
    if user.nstatus == 0:
        raise ValueError("Akun ini tidak aktif. Silakan hubungi admin.")
    if user.nstatus != 2: # Status lain selain Pending
        raise ValueError(f"Tautan aktivasi ini tidak dapat digunakan (Status Akun: {user.nstatus}).")

    # 6. Kalo Lolos: Aktifkan User & Nonaktifkan Token
    user.nstatus = 1 # Jadi Aktif
    user.vmodified_by = "system-activation"
    user.dsort_at = now_wib()
    
    db_token.nstatus = 0 # Nonaktifkan token setelah dipakai

    try:
        db.commit()
        db.refresh(user)
        auditLogController.create_security_log(
            db=db, nid_user=user.nid, action="ACCOUNT_ACTIVATION_SUCCESS", 
            request=request, details="Public registration verified"
        )
        db.commit()
    except Exception as commit_error:
        db.rollback()
        print(f"Error activating registered user {user.vemail}: {commit_error}")
        raise ValueError("Gagal mengaktifkan akun. Silakan coba lagi.")

    print(f"✅ User {user.vemail} (ID: {user.nid}) has been successfully activated from public registration.")
    return user

def verify_and_update_email(db: Session, token: str, request: Request):
    # Logika fungsi ini tidak berubah
    # Cari token verifikasi email (tipe 4)
    db_token = db.query(tokenModel.Token).filter(
        tokenModel.Token.vcode == token,
        tokenModel.Token.ntoken_type == 4 # Pastikan tipe ganti email
    ).first()

    if not db_token:
        raise ValueError("Token verifikasi tidak valid atau tidak ditemukan.")
    if db_token.nstatus == 0:
        raise ValueError("Tautan verifikasi ini sudah pernah digunakan.")

    # Cek expired
    expires_at_aware = to_wib(db_token.dexpires_at)
    if expires_at_aware < now_wib():
        db_token.nstatus = 0 # Nonaktifkan token expired
        db.commit()
        raise ValueError("Tautan verifikasi sudah kedaluwarsa.")

    # Cari user terkait
    user_to_update = db.query(models.User).filter(models.User.nid == db_token.nid_user).first()
    if not user_to_update:
        # Aneh, tapi nonaktifkan tokennya
        db_token.nstatus = 0
        db.commit()
        raise ValueError("Pengguna yang terkait dengan token ini tidak ditemukan.")

    # Cek lagi apakah email baru udah dipake user lain (jaga-jaga kalo ada race condition)
    new_email = db_token.vnew_email
    if not new_email: # Seharusnya gak mungkin, tapi cek aja
         db_token.nstatus = 0
         db.commit()
         raise ValueError("Token verifikasi tidak valid (tidak ada email baru).")

    existing_user_with_new_email = db.query(models.User).filter(
        models.User.vemail == new_email,
        models.User.nid != user_to_update.nid # Kecualikan user yg sedang update
    ).first()
    if existing_user_with_new_email:
         db_token.nstatus = 0 # Nonaktifkan token yg gak bisa dipake ini
         db.commit()
         raise ValueError("Gagal memperbarui. Alamat email baru sudah digunakan oleh pengguna lain.")

    # Update email user
    user_to_update.vemail = new_email
    user_to_update.vmodified_by = "system-email-verify"
    user_to_update.dsort_at = now_wib()
    # Nonaktifkan token & hapus email dari token
    db_token.nstatus = 0
    db_token.vnew_email = None # Hapus email dari token setelah dipakai

    try:
        db.commit()
        db.refresh(user_to_update)
        auditLogController.create_security_log(
            db=db, nid_user=user_to_update.nid, action="EMAIL_CHANGE_VERIFIED", 
            request=request, details=f"Email successfully changed to {new_email}"
        )
        db.commit()
        print(f"✅ Email for user {user_to_update.vcode} successfully updated to {user_to_update.vemail}.")
        return user_to_update
    except IntegrityError as e: # Jaga-jaga kalo ada constraint lain
        db.rollback()
        error_info = str(e.orig).lower()
        print(f"IntegrityError during email update confirmation: {error_info}")
        # Kemungkinan emailnya udah dipake pas race condition
        raise ValueError("Gagal memperbarui email. Email baru mungkin sudah digunakan.")
    except Exception as commit_error:
        db.rollback()
        print(f"Error committing email update for {user_to_update.vcode}: {commit_error}")
        raise ValueError("Gagal memperbarui email. Silakan coba lagi.")


# --- Fungsi Scheduler (sedikit penyesuaian) ---
def schedule_token_expiry(sched, db_factory, user_id: int, token_id: int, task_type: str, delay_seconds: int): # Tambah delay_seconds
    job_id = f"{task_type}_{token_id}" # ID unik buat job

    # Hapus job lama kalo ada (misal resend activation)
    if sched.get_job(job_id):
        try:
            sched.remove_job(job_id)
            print(f"[SCHEDULER] Removed existing job: {job_id}")
        except Exception as remove_err:
             print(f"[SCHEDULER] Warning: Failed to remove existing job {job_id}. Error: {remove_err}")


    # Hitung waktu jalan (dari sekarang + delay)
    run_time = datetime.now(jakarta_tz) + timedelta(seconds=delay_seconds)

    # Definisikan fungsi yg akan dijalankan scheduler
    @sched.scheduled_job("date", run_date=run_time, id=job_id)
    def expire_token_job():
        # Dapetin session DB baru di dalam job
        db = db_factory()
        try:
            # Cari token berdasarkan ID
            token = db.query(tokenModel.Token).filter(tokenModel.Token.nid == token_id).first()

            # Kalo token gak ada ATAU udah gak aktif (status 0), skip aja
            if not token or token.nstatus != 1:
                sys.stdout.write(f"\n[SCHEDULER SKIP] Job {job_id} skipped, token (ID: {token_id}) not found or already inactive.\n")
                sys.stdout.flush()
                return

            # Kalo token masih aktif dan udah waktunya expired
            print(f"\n[SCHEDULER RUN] Running job {job_id} for token ID: {token_id}")

            if task_type == 'user_activation':
                # Cari user terkait
                user = db.query(models.User).filter(models.User.nid == user_id).first()
                # Kalo user ada DAN statusnya masih Pending (2)
                if user and user.nstatus == 2:
                    user.nstatus = 3 # Ubah jadi Expired
                    user.vmodified_by = "system-scheduler-expire"
                    user.dsort_at = now_wib()
                    token.nstatus = 0 # Nonaktifkan token
                    auditLogController.create_security_log(
                        db=db, nid_user=user.nid, action="ACCOUNT_EXPIRED_BY_SCHEDULER", 
                        request=None, details=f"Activation token {token_id} expired."
                    )
                    db.commit()
                    sys.stdout.write(f"[SCHEDULER EXPIRE] User activation for {user.vemail} (ID: {user_id}) has expired via job {job_id}.\n")
                    sys.stdout.flush()
                elif user and user.nstatus == 1:
                     # User udah aktif, token gak relevan lagi, nonaktifkan aja
                     token.nstatus = 0
                     db.commit()
                     sys.stdout.write(f"[SCHEDULER SKIP] Job {job_id} skipped, user {user.vemail} (ID: {user_id}) already active. Token deactivated.\n")
                     sys.stdout.flush()
                elif user and user.nstatus == 3:
                     # User udah expired (mungkin dari job lain atau manual), token nonaktifkan aja
                     token.nstatus = 0
                     db.commit()
                     sys.stdout.write(f"[SCHEDULER SKIP] Job {job_id} skipped, user {user.vemail} (ID: {user_id}) already expired. Token deactivated.\n")
                     sys.stdout.flush()
                elif not user:
                     # User gak ketemu, aneh. Nonaktifkan token aja.
                     token.nstatus = 0
                     db.commit()
                     sys.stdout.write(f"[SCHEDULER SKIP] Job {job_id} skipped, user (ID: {user_id}) not found. Token deactivated.\n")
                     sys.stdout.flush()


            elif task_type == 'email_change':
                # Cukup nonaktifkan token verifikasi email
                token.nstatus = 0
                auditLogController.create_security_log(
                    db=db, nid_user=token.nid_user, action="EMAIL_CHANGE_TOKEN_EXPIRED",
                    request=None, details=f"Email change token {token_id} expired."
                )
                db.commit()
                sys.stdout.write(f"[SCHEDULER EXPIRE] Email change token (ID: {token_id}) for UserID={user_id} has expired via job {job_id}.\n")
                sys.stdout.flush()
            
            elif task_type == 'password_reset':
                # Cukup nonaktifkan token reset password
                token.nstatus = 0
                auditLogController.create_security_log(
                    db=db, nid_user=token.nid_user, action="PASSWORD_RESET_TOKEN_EXPIRED",
                    request=None, details=f"Password reset token {token_id} expired."
                )
                db.commit()
                sys.stdout.write(f"[SCHEDULER EXPIRE] Password reset token (ID: {token_id}) for UserID={user_id} has expired via job {job_id}.\n")
                sys.stdout.flush()

            # Tambahin task type lain kalo perlu

        except Exception as job_error:
             # Tangani error di dalam job
             db.rollback() # Rollback kalo ada error pas commit
             sys.stderr.write(f"\n[SCHEDULER ERROR] Error in job {job_id}: {job_error}\n")
             sys.stderr.flush()
        finally:
            db.close() # Pastikan session ditutup

    # --- Countdown Display (Opsional, buat debug di console) ---
    # def countdown_display():
    #     total = int(delay_seconds)
    #     check_interval = 15 # Cek status token tiap 15 detik

    #     while total > 0:
    #         # Cek status token secara berkala
    #         if total % check_interval == 0:
    #             try:
    #                 db_check = db_factory()
    #                 token = db_check.query(tokenModel.Token).filter(tokenModel.Token.nid == token_id).first()
    #                 if not token or token.nstatus != 1:
    #                     sys.stdout.write(f"\r[SCHEDULER STOP] Countdown for job {job_id} stopped, token (ID: {token_id}) became inactive.{' ' * 20}\n")
    #                     sys.stdout.flush()
    #                     db_check.close()
    #                     return # Stop countdown kalo token udah gak aktif
    #                 db_check.close()
    #             except Exception as e:
    #                 print(f"\nError checking token status in countdown for job {job_id}: {e}")
    #                 # Lanjutkan countdown aja

    #         mins, secs = divmod(total, 60)
    #         hours, mins = divmod(mins, 60)
    #         time_str = f"{hours:02d}:{mins:02d}:{secs:02d}"

    #         sys.stdout.write(f"\r[SCHEDULER COUNTDOWN] Job {job_id} will trigger in {time_str} ")
    #         sys.stdout.flush()
    #         try:
    #              time.sleep(1)
    #         except KeyboardInterrupt:
    #              sys.stdout.write(f"\nCountdown interrupted for {job_id}.\n")
    #              sys.stdout.flush()
    #              return
    #         total -= 1

    #     sys.stdout.write(f"\r[SCHEDULER TRIGGER] Job {job_id} trigger time reached.{' ' * 40}\n")
    #     sys.stdout.flush()

    # # Jalankan countdown di thread terpisah biar gak block
    # countdown_thread = threading.Thread(target=countdown_display)
    # countdown_thread.start()
    # --- End Countdown Display ---

    print(f"[SCHEDULER] Job '{job_id}' scheduled to run at {run_time.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")


def start_scheduler(app):
    # Logika fungsi ini tidak berubah
    if not hasattr(app.state, "scheduler") or not app.state.scheduler.running:
        try:
          sched = scheduler.AsyncIOScheduler(timezone=str(jakarta_tz)) # Set timezone
          sched.start()
          app.state.scheduler = sched
          print("✅ Scheduler started and ready for dynamic per-user jobs.")
        except Exception as e:
          print(f"❌ Failed to start scheduler: {e}")
          app.state.scheduler = None # Set None kalo gagal start
    else:
        print("ℹ️ Scheduler already running.")


# --- Fungsi Helper Get User ---
def get_user_by_code(db: Session, user_code: str):
    return db.query(models.User).filter(models.User.vcode == user_code).first()

def get_user_by_email(db: Session, email: str):
    # Tambah .lower() buat case-insensitive
    return db.query(models.User).filter(models.User.vemail.ilike(email)).first()

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.nid == user_id).first()

def get_admin_scope(db: Session, current_user: models.User):
    """
    Menentukan scope akses admin.
    Return:
        - is_global (bool): True jika SA
        - allowed_dept_ids (list[int]): List ID departemen yang boleh diakses (jika ADM)
    """
    # Ambil semua akses aktif user ini
    user_accesses = db.query(userAccessModel.UserAccess).join(
        rolesModel.Role, userAccessModel.UserAccess.nid_role == rolesModel.Role.nid
    ).filter(
        userAccessModel.UserAccess.nid_user == current_user.nid,
        userAccessModel.UserAccess.nstatus == 1
    ).all()

    is_global = False
    allowed_dept_ids = set()

    for access in user_accesses:
        role_code = access.role.vcode
        if role_code == 'SA':
            is_global = True
            break # Kalau udah SA, gak perlu cek yang lain, dia dewa
        elif role_code == 'ADM':
            if access.nid_department:
                allowed_dept_ids.add(access.nid_department)

    if not is_global and not allowed_dept_ids:
        # Kalau bukan SA dan gak punya departemen yang dikelola sebagai ADM
        # (atau role-nya cuma PIC/VSTR)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak memiliki hak akses Admin atau Superadmin yang valid."
        )

    return is_global, list(allowed_dept_ids)

# --- Fungsi Get List Users ---
def get_users(
    db: Session,
    current_user: models.User, 
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    nstatus: int | None = None,
    vname: str | None = None,
    vemail: str | None = None,
    vcode: str | None = None,
):
    # 1. Tentukan Scope
    is_global, allowed_dept_ids = get_admin_scope(db, current_user)

    # 2. Build Base Query
    query = db.query(models.User)

    # 3. Apply Context-Aware Filtering
    if not is_global:
        # CASE: Admin Departemen (ADM)
        # Logic: Hanya tampilkan user yang punya role VSTR/PIC di departemen yang dikelola Admin
        
        # Join ke UserAccess dan Role untuk filter target user
        query = query.join(
            userAccessModel.UserAccess, models.User.nid == userAccessModel.UserAccess.nid_user
        ).join(
            rolesModel.Role, userAccessModel.UserAccess.nid_role == rolesModel.Role.nid
        ).filter(
            # Filter 1: Target user harus ada di departemen si Admin
            userAccessModel.UserAccess.nid_department.in_(allowed_dept_ids),
            # Filter 2: Target user role-nya harus VSTR atau PIC
            rolesModel.Role.vcode.in_(['VSTR', 'PIC']),
            # Filter 3: Akses target user harus aktif
            userAccessModel.UserAccess.nstatus == 1
        ).distinct() # Penting! Biar user gak muncul dobel kalau punya multiple roles di dept sama
    
    # --- Filter Standar (Search, dll) tetap jalan seperti biasa ---
    if search:
        search_filter = or_(
            models.User.vname.ilike(f"%{search}%"),
            models.User.vcode.ilike(f"%{search}%"),
            models.User.vemail.ilike(f"%{search}%"),
        )
        query = query.filter(search_filter)

    if vname:
        query = query.filter(models.User.vname.ilike(f"%{vname}%"))
    if vemail:
        query = query.filter(models.User.vemail.ilike(f"%{vemail}%"))
    if vcode:
        query = query.filter(models.User.vcode.ilike(f"%{vcode}%"))

    if nstatus is not None:
        if nstatus in [0, 1, 2, 3]:
            query = query.filter(models.User.nstatus == nstatus)

    # Sorting & Pagination
    total = query.count()
    query = query.order_by(models.User.dsort_at.desc())
    data = query.offset(skip).limit(limit).all()
    
    return {"data": data, "total": total}

# --- Fungsi Delete User (Soft Delete ---
def delete_user(db: Session, user_vcode: str, current_user: str):
    db_user = get_user_by_code(db, user_code=user_vcode)
    if db_user:
        if db_user.nstatus == 0:
            print(f"User {user_vcode} is already inactive.")
            return db_user # Kembalikan aja user yg udah inactive
        db_user.nstatus = 0 # Set jadi Inactive
        db_user.vmodified_by = current_user
        db_user.dsort_at = now_wib()
        try:
             db.commit()
             db.refresh(db_user)
             print(f"✅ User {user_vcode} soft deleted successfully.")
        except Exception as e:
             db.rollback()
             print(f"Error soft deleting user {user_vcode}: {e}")
             # Bisa raise error atau return None tergantung flow yg diinginkan
             return None # Gagal delete
    else:
         print(f"Soft delete failed: User {user_vcode} not found.")
    return db_user

# --- Fungsi Get Users for Dropdown ---
def get_all_users_for_dropdown(db: Session):
    # Ambil user yg aktif aja (nstatus=1)
    users = db.query(models.User).order_by(models.User.vemail).all()
    return {"data": users}

def get_all_active_users_for_dropdown(db: Session):
    # Ambil user yg aktif aja (nstatus=1)
    users = db.query(models.User).filter(models.User.nstatus == 1).order_by(models.User.vemail).all()
    return {"data": users}


# --- Fungsi Verifikasi Token ---
def verify_activation_token(db: Session, token: str):
    # Logika fungsi ini tidak berubah
    db_token = (
        db.query(tokenModel.Token)
        .filter(
            tokenModel.Token.vcode == token,
            tokenModel.Token.ntoken_type == 1 # Tipe Aktivasi
        )
        .first()
    )

    if not db_token:
        return {"valid": False, "reason": "Token tidak ditemukan."}
    if db_token.nstatus == 0:
        return {"valid": False, "reason": "Token sudah digunakan atau tidak aktif."}

    # Cek expired
    expires_at_aware = to_wib(db_token.dexpires_at)
    if expires_at_aware < now_wib():
        # Update status user jadi Expired (3) kalo masih Pending (2)
        user_to_update = db.query(models.User).filter(models.User.nid == db_token.nid_user).first()
        if user_to_update and user_to_update.nstatus == 2:
            user_to_update.nstatus = 3
            user_to_update.vmodified_by = "system-token-verify-expired"
            user_to_update.dsort_at = now_wib()
            db_token.nstatus = 0 # Nonaktifkan token
            try:
                db.commit()
            except Exception:
                db.rollback() # Abaikan error commit di sini
        elif db_token.nstatus == 1: # Kalo token belum dinonaktifkan
             db_token.nstatus = 0
             try:
                 db.commit()
             except Exception:
                 db.rollback()
        return {"valid": False, "reason": "Token sudah kedaluwarsa."}

    # Cek user terkait
    user = db.query(models.User).filter(models.User.nid == db_token.nid_user).first()
    if not user:
        db_token.nstatus = 0 # Nonaktifkan token aneh ini
        db.commit()
        return {"valid": False, "reason": "Pengguna terkait tidak ditemukan."}

    # Cek status user, harus Pending (2)
    if user.nstatus != 2:
        # Token ini gak relevan lagi, nonaktifkan
        if db_token.nstatus == 1:
            db_token.nstatus = 0
            db.commit()

        if user.nstatus == 1:
             return {"valid": False, "reason": "Pengguna sudah aktif."}
        elif user.nstatus == 3:
             return {"valid": False, "reason": "Aktivasi pengguna sudah kedaluwarsa."}
        elif user.nstatus == 0:
             return {"valid": False, "reason": "Akun pengguna tidak aktif."}
        else: # Status lain yg mungkin ada
             return {"valid": False, "reason": f"Status pengguna tidak valid untuk aktivasi ({user.nstatus})."}


    # Kalo lolos semua cek di atas
    return {"valid": True, "reason": "Token aktif dan valid."}

# --- Fungsi Verifikasi Password ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    # Tambahkan pepper sebelum verifikasi
    password_with_pepper = plain_password + PASSWORD_PEPPER
    try:
      # Verifikasi password yg udah di-pepper dengan hash di DB
      return pwd_context.verify(password_with_pepper, hashed_password)
    except Exception as e:
      # Tangani kalo ada error pas verifikasi (misal hash korup atau algoritma beda)
      print(f"Error verifying password: {e}")
      return False

# --- Fungsi Hash Password ---
def get_password_hash(password: str) -> str:
    if not password:
        raise ValueError("Password tidak boleh kosong")
    # Tambahkan pepper sebelum hash
    password_with_pepper = password + PASSWORD_PEPPER
    # Hash password yg udah di-pepper
    return pwd_context.hash(password_with_pepper)

async def request_password_reset(db: Session, email: str,request: Request, app=None, db_factory=None):
    """
    Memproses permintaan reset password.
    Akan selalu return sukses (secara diam-diam) 
    untuk mencegah email enumeration.
    """
    user = get_user_by_email(db, email=email)

    # Security: Jangan kasih tau kalo email gak ada atau gak aktif
    # Cukup proses kalo user-nya valid (status 1 = Aktif)
    if user and user.nstatus == 1:
        
        # Buat token reset (Tipe 3)
        reset_token_str = secrets.token_urlsafe(32)
        expires_at = now_wib() + timedelta(hours=1) # Reset token berlaku 1 jam

        # Nonaktifkan token reset (Tipe 3) lama yg mungkin masih aktif
        db.query(tokenModel.Token).filter(
            tokenModel.Token.nid_user == user.nid,
            tokenModel.Token.ntoken_type == 3, # Tipe 3 = Password Reset
            tokenModel.Token.nstatus == 1
        ).update({"nstatus": 0})

        db_token = tokenModel.Token(
            nid_user=user.nid,
            ntoken_type=3, # Tipe 3 = Password Reset
            vcode=reset_token_str,
            dexpires_at=expires_at,
            nstatus=1 # Aktif
        )
        db.add(db_token)
        
        try:
            db.commit()
            db.refresh(db_token)
            auditLogController.create_security_log(
                db=db, nid_user=user.nid, action="PASSWORD_RESET_REQUEST", 
                request=request
            )
            db.commit()
        except Exception as commit_error:
            db.rollback()
            print(f"Error committing password reset token for {user.vemail}: {commit_error}")
            # Gagal di sini, tapi tetep return sukses ke user
            return {"message": "Permintaan reset password telah diproses."}

        # Kirim email
        try:
            await send_password_reset_email(
                recipient_email=user.vemail,
                user_name=user.vname,
                reset_token=reset_token_str,
            )
        except Exception as e:
            print(f"ERROR: Reset token for {user.vemail} created, BUT failed to send email. Error: {e}")
            # Gagal kirim email, tapi user nggak perlu tau

        # Jadwalkan expiry token (1 jam = 3600 detik)
        if app and hasattr(app.state, "scheduler") and db_factory:
            schedule_token_expiry(
                sched=app.state.scheduler,
                db_factory=db_factory,
                user_id=user.nid,
                token_id=db_token.nid,
                task_type='password_reset', # Task type baru
                delay_seconds=3600 
            )
        
        print(f"🔑 Password reset initiated for {user.vemail}. Token expires in 1 hour.")

    else:
        # User gak ketemu atau gak aktif
        print(f"Password reset request for '{email}' (Not Found or Inactive). Silently succeeding.")
        auditLogController.create_security_log(
            db=db, nid_user=None, action="PASSWORD_RESET_REQUEST_FAILED", 
            request=request, details=f"Attempted email: {email}, reason: user not found/inactive"
        )
        db.commit()
    
    # Selalu kembalikan pesan generik
    return {"message": "Jika email Anda terdaftar, instruksi reset password akan dikirim."}


def verify_reset_token(db: Session, token: str):
    """
    Memvalidasi token reset password (Tipe 3) untuk UI.
    Mirip verify_activation_token tapi untuk ntoken_type=3 dan nstatus=1 (Aktif).
    """
    db_token = (
        db.query(tokenModel.Token)
        .filter(
            tokenModel.Token.vcode == token,
            tokenModel.Token.ntoken_type == 3 # Tipe 3 = Password Reset
        )
        .first()
    )

    if not db_token:
        return {"valid": False, "reason": "Token tidak valid atau tidak ditemukan."}
    if db_token.nstatus == 0:
        return {"valid": False, "reason": "Tautan ini sudah digunakan."}

    # Cek expired
    expires_at_aware = to_wib(db_token.dexpires_at)
    if expires_at_aware < now_wib():
        if db_token.nstatus == 1:
            db_token.nstatus = 0 # Nonaktifkan token
            try:
                db.commit()
            except Exception:
                db.rollback()
        return {"valid": False, "reason": "Tautan ini sudah kedaluwarsa."}

    # Cek user terkait
    user = db.query(models.User).filter(models.User.nid == db_token.nid_user).first()
    if not user:
        db_token.nstatus = 0 
        db.commit()
        return {"valid": False, "reason": "Pengguna terkait tidak ditemukan."}

    # Cek status user, harus Aktif (1)
    if user.nstatus != 1:
        if db_token.nstatus == 1:
            db_token.nstatus = 0
            db.commit()
        
        status_map = {0: "Tidak Aktif", 2: "Pending", 3: "Kedaluwarsa"}
        reason = status_map.get(user.nstatus, f"Status {user.nstatus}")
        return {"valid": False, "reason": f"Akun pengguna saat ini {reason}."}

    # Kalo lolos semua cek di atas
    return {"valid": True, "reason": "Token aktif dan valid."}


def reset_password(db: Session, password_data: schema.ResetPassword, request: Request):
    """
    Mengatur password baru menggunakan token reset (Tipe 3).
    Mirip set_initial_password tapi untuk ntoken_type=3 dan user nstatus=1.
    """
    # Cari token reset (tipe 3)
    db_token = db.query(tokenModel.Token).filter(
        tokenModel.Token.vcode == password_data.token,
        tokenModel.Token.ntoken_type == 3 # Pastikan tipe reset password
    ).first()

    if not db_token:
        raise ValueError("Token tidak valid atau tidak ditemukan.")
    if db_token.nstatus == 0:
        raise ValueError("Tautan reset password ini sudah pernah digunakan.")

    # Cek expired
    expires_at_aware = to_wib(db_token.dexpires_at)
    if expires_at_aware < now_wib():
        if db_token.nstatus == 1:
            db_token.nstatus = 0
            db.commit()
        raise ValueError("Tautan reset password sudah kedaluwarsa.")

    # Cari user terkait
    user = db.query(models.User).filter(models.User.nid == db_token.nid_user).first()
    if not user:
        db_token.nstatus = 0 
        db.commit()
        raise ValueError("Pengguna yang terkait dengan token ini tidak ditemukan.")

    # Pastikan user-nya Aktif (status 1)
    if user.nstatus != 1:
        db_token.nstatus = 0 
        db.commit()
        status_map = {0: "Tidak Aktif", 2: "Pending", 3: "Kedaluwarsa"}
        current_status = status_map.get(user.nstatus, f"Status {user.nstatus}")
        raise ValueError(f"Tidak dapat mereset password karena status akun adalah '{current_status}'.")

    # Set password baru dan nonaktifkan token
    user.vpassword = get_password_hash(password_data.password)
    user.vmodified_by = "system-password-reset"
    user.dsort_at = now_wib()
    
    db_token.nstatus = 0 # Nonaktifkan token setelah dipakai

    try:
        db.commit()
        db.refresh(user)
        auditLogController.create_security_log(
            db=db, nid_user=user.nid, action="PASSWORD_RESET_SUCCESS", 
            request=request
        )
        db.commit()
    except Exception as commit_error:
        db.rollback()
        print(f"Error resetting password for {user.vemail}: {commit_error}")
        raise ValueError("Gagal menyimpan password baru. Silakan coba lagi.")

    print(f"✅ Password for user {user.vemail} (ID: {user.nid}) has been successfully reset.")
    return user

def get_scoped_users_for_dropdown(db: Session, current_user: models.User):
    """
    [SCOPED] Mengambil SEMUA user (Active/Inactive) sesuai Scope Admin.
    """
    return _get_users_by_scope_logic(db, current_user, only_active=False)

def get_scoped_active_users_for_dropdown(db: Session, current_user: models.User):
    """
    [SCOPED] Mengambil user AKTIF saja sesuai Scope Admin.
    Biasanya dipake buat dropdown 'Add User to Lab'.
    """
    return _get_users_by_scope_logic(db, current_user, only_active=True)


# --- Helper Internal Logic ---
def _get_users_by_scope_logic(db: Session, current_user: models.User, only_active: bool):
    # 1. Cek Scope User (SA atau ADM Dept mana?)
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
    query = db.query(models.User)
    
    if only_active:
        query = query.filter(models.User.nstatus == 1)

    # 3. Apply Filter Scope (Jika BUKAN SA)
    if not is_global:
        if not allowed_dept_ids:
            # Admin tanpa departemen = return kosong
            return {"data": []}

        # Join ke UserAccess -> Filter user yang terdaftar di departemen si Admin
        query = query.join(
            userAccessModel.UserAccess, models.User.nid == userAccessModel.UserAccess.nid_user
        ).join(
            rolesModel.Role, userAccessModel.UserAccess.nid_role == rolesModel.Role.nid
        ).filter(
            # Filter 1: User harus punya akses di departemen Admin
            userAccessModel.UserAccess.nid_department.in_(allowed_dept_ids),
            
            # Filter 2 (Blacklist): Jangan tampilkan SA & ADM lain
            rolesModel.Role.vcode.notin_(['SA', 'ADM']),
            
            # Filter 3: Akses user-nya harus aktif
            userAccessModel.UserAccess.nstatus == 1
        ).distinct()

    # 4. Order & Return
    query = query.order_by(models.User.vname.asc())
    data = query.all()
    
    return {"data": data}