from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Form # Tambah Request, Response, Form
# from fastapi.security import OAuth2PasswordRequestForm # Gak dipake lagi di /token
from sqlalchemy.orm import Session
from typing import List, Optional, Annotated 
from datetime import timedelta, datetime
from ..controller import userAccessController 
from ..schemas import usersSchema as schema
from ..controller import usersController
from ..models import usersModel as models
from ..database import SessionLocal # Import SessionLocal untuk db_factory

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

@router.post("/token") # Hapus response_model=schema.TokenResponse
async def login_for_access_token(
    response: Response, # Inject Response object
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
        user = usersController.authenticate_user(db, email=username, password=password)
        if not user:
            print(f"[API /token] Login failed for {username}: Invalid credentials.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email atau password salah",
                headers={"WWW-Authenticate": "Bearer"},
            )

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

        user_response = schema.User.model_validate(user)
        print(f"[API /token] Login successful for {user.vemail}. Returning user data.")
        return {"user": user_response}

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

@router.post("/refresh_token", response_model=schema.NewAccessTokenResponse)
async def refresh_token_endpoint(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Endpoint refresh token. Baca refresh token dari cookie, validasi,
    dan set access token baru di cookie.
    """
    print("[API /refresh_token] Refresh token request received.")
    refresh_token_from_cookie = request.cookies.get("refresh_token")
    if not refresh_token_from_cookie:
         print("[API /refresh_token] Refresh failed: Refresh token cookie not found.")
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesi tidak valid atau sudah berakhir (RF Token Missing).",
        )

    try:
        new_access_token, user_nid = await usersController.refresh_access_token(
            db=db, refresh_token=refresh_token_from_cookie
        )
        print(f"[API /refresh_token] Refresh successful for user NID: {user_nid}.")

        # Set cookie access token baru
        response.set_cookie(
            key="access_token",
            value=new_access_token,
            httponly=True,
            max_age=ACCESS_TOKEN_COOKIE_EXPIRE_SECONDS,
            expires=ACCESS_TOKEN_COOKIE_EXPIRE_SECONDS,
            path="/",
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE
        )
        print(f"[API /refresh_token] New access token cookie set.")

        # Kembalikan response body (opsional)
        return {"access_token": new_access_token, "token_type": "bearer"}

    except HTTPException as e:
         print(f"[API /refresh_token] Refresh failed: {e.detail} (Status: {e.status_code})")
         if e.status_code == status.HTTP_401_UNAUTHORIZED:
             print("[API /refresh_token] Deleting invalid refresh and access token cookies.")
             response.delete_cookie("refresh_token", path="/users/refresh_token", secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)
             response.delete_cookie("access_token", path="/", secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)
             e.detail = "Sesi tidak valid atau sudah berakhir (RF Invalid/Expired)."
         raise e
    except Exception as e:
        print(f"[API /refresh_token] Unexpected error during token refresh: {e}")
        response.delete_cookie("refresh_token", path="/users/refresh_token", secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)
        response.delete_cookie("access_token", path="/", secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal memperbarui sesi."
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
    print(f"[API /admin-create] Request received from user: {current_user.vemail}")
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    print(f"[API /admin-create] User roles: {user_roles}")

    allowed_roles = {"SA"} # Sesuaikan role yg dibolehkan
    if not any(role in allowed_roles for role in user_roles):
        print(f"[API /admin-create] Forbidden: User {current_user.vemail} does not have required roles.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk membuat pengguna baru."
        )

    try:
        new_user = await usersController.create_user_by_admin(
            db=db, user_data=user_data, app=request.app, db_factory=SessionLocal
        )
        print(f"[API /admin-create] User {new_user.vemail} created successfully.")
        return new_user
    except ValueError as e:
        print(f"[API /admin-create] Failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
         print(f"[API /admin-create] Unexpected error: {e}")
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal membuat pengguna.")


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
    target_user = usersController.get_user_by_code(db, user_code=user_vcode)

    if not target_user:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pengguna yang akan diupdate tidak ditemukan.")

    is_updating_self = current_user.vcode == user_vcode
    allowed_admin_roles = {"SA"} # Sesuaikan
    is_allowed_admin = any(role in allowed_admin_roles for role in user_roles)

    if not is_updating_self and not is_allowed_admin:
        print(f"[API PUT /users/{user_vcode}] Forbidden: User {current_user.vemail} cannot update user {user_vcode}.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk mengupdate pengguna ini."
        )

    try:
        db_user = await usersController.update_user(
            db=db, user_vcode=user_vcode, user=user_update_data, app=request.app, db_factory=SessionLocal
        )
        if db_user is None:
            print(f"[API PUT /users/{user_vcode}] Update failed: User not found.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
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
    response: Response, # Inject response
    db: Session = Depends(get_db),
    current_user: schema.User = Depends(usersController.get_current_active_user_from_cookie),
):
    """Melakukan soft delete user (membutuhkan hak akses)."""
    print(f"[API DELETE /users/{user_vcode}] Request received from user: {current_user.vemail}")
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)
    print(f"[API DELETE /users/{user_vcode}] User roles: {user_roles}")

    allowed_roles = {"SA"} # Sesuaikan
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

    deleted_user = usersController.delete_user(db=db, user_vcode=user_vcode)

    if deleted_user is None or deleted_user.nstatus != 0:
        print(f"[API DELETE /users/{user_vcode}] Delete failed: User not found or internal error during delete.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pengguna tidak ditemukan atau gagal dihapus.")

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

    allowed_roles = {"SA", "ADM"} # Sesuaikan
    if not any(role in allowed_roles for role in user_roles):
        print(f"[API GET /users/] Forbidden: User {current_user.vemail} cannot view user list.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk melihat daftar pengguna."
        )

    users_data = usersController.get_users(
        db=db, skip=skip, limit=limit, search=search,
        nstatus=nstatus, vname=name, vemail=email, vcode=code
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


# --- Endpoint Publik (tidak butuh autentikasi) ---

@router.post("/set-initial-password", response_model=schema.User)
def set_user_initial_password(password_data: schema.SetInitialPassword, db: Session = Depends(get_db)):
    """Endpoint publik untuk user set password awal pakai token aktivasi."""
    print(f"[API /set-initial-password] Request received for token: {password_data.token[:5]}...")
    try:
        updated_user = usersController.set_initial_password(db=db, password_data=password_data)
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
def verify_user_email_change(token: str, db: Session = Depends(get_db)):
    """Endpoint publik untuk verifikasi perubahan email via token."""
    print(f"[API /verify-email-change/] Request received for token: {token[:5]}...")
    try:
        updated_user = usersController.verify_and_update_email(db=db, token=token)
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
async def logout(response: Response):
    """Menghapus cookie access dan refresh token."""
    print("[API /logout] Logout request received. Deleting token cookies.")
    response.delete_cookie("access_token", path="/", secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)
    response.delete_cookie("refresh_token", path="/users/refresh_token", secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)
    return {"message": "Logout successful"}