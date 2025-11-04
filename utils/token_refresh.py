from dataclasses import dataclass
from typing import Any, Optional, Tuple
from fastapi import HTTPException, status, Request, Response
from sqlalchemy.orm import Session

@dataclass(frozen=True)
class RefreshConfig:
    access_cookie_key: str = "access_token"
    refresh_cookie_key: str = "refresh_token"
    # cookie options
    access_cookie_path: str = "/"
    refresh_cookie_path: str = "/users/refresh_token"
    cookie_secure: bool = True          # sesuaikan dengan setting
    cookie_samesite: str = "lax"        # "lax" / "strict" / "none"
    access_cookie_max_age: int = 1800

async def refresh_access_cookie(
    *,
    request: Request,
    response: Response,
    db: Session,
    users_controller: Any,   # harus punya method: refresh_access_token(db, refresh_token) -> (new_access_token, user_nid)s
    cfg: RefreshConfig
) -> dict:
    """
    Baca refresh_token dari cookie, validasi via users_controller,
    set access_token baru di cookie, dan balikan payload JSON.
    Lempar HTTPException sesuai kondisi error.
    """
    print("[UTIL refresh_access_cookie] Refresh token request received.")
    refresh_token_from_cookie: Optional[str] = request.cookies.get(cfg.refresh_cookie_key)

    if not refresh_token_from_cookie:
        print("[UTIL refresh_access_cookie] Refresh failed: Refresh token cookie not found.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesi tidak valid atau sudah berakhir (RF Token Missing).",
        )

    try:
        new_access_token, user_nid = await _do_refresh(
            db=db,
            users_controller=users_controller,
            refresh_token=refresh_token_from_cookie,
        )
        print(f"[UTIL refresh_access_cookie] Refresh successful for user NID: {user_nid}.")

        # set cookie access token baru
        response.set_cookie(
            key=cfg.access_cookie_key,
            value=new_access_token,
            httponly=True,
            max_age=cfg.access_cookie_max_age,
            expires=cfg.access_cookie_max_age,
            path=cfg.access_cookie_path,
            secure=cfg.cookie_secure,
            samesite=cfg.cookie_samesite,
        )
        print("[UTIL refresh_access_cookie] New access token cookie set.")

        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "access_expires_in": cfg.access_cookie_max_age,
        }

    except HTTPException as e:
        print(f"[UTIL refresh_access_cookie] Refresh failed: {e.detail} (Status: {e.status_code})")
        if e.status_code == status.HTTP_401_UNAUTHORIZED:
            # Hapus cookies kalau refresh invalid/expired
            print("[UTIL refresh_access_cookie] Deleting invalid refresh and access token cookies.")
            response.delete_cookie(
                cfg.refresh_cookie_key,
                path=cfg.refresh_cookie_path,
                secure=cfg.cookie_secure,
                samesite=cfg.cookie_samesite,
            )
            response.delete_cookie(
                cfg.access_cookie_key,
                path=cfg.access_cookie_path,
                secure=cfg.cookie_secure,
                samesite=cfg.cookie_samesite,
            )
            # tulis ulang detail agar konsisten
            e.detail = "Sesi tidak valid atau sudah berakhir (RF Invalid/Expired)."
        raise e

    except Exception as e:
        print(f"[UTIL refresh_access_cookie] Unexpected error during token refresh: {e}")
        # safety: bersihkan dua-duanya
        response.delete_cookie(
            cfg.refresh_cookie_key,
            path=cfg.refresh_cookie_path,
            secure=cfg.cookie_secure,
            samesite=cfg.cookie_samesite,
        )
        response.delete_cookie(
            cfg.access_cookie_key,
            path=cfg.access_cookie_path,
            secure=cfg.cookie_secure,
            samesite=cfg.cookie_samesite,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal memperbarui sesi."
        )

async def _do_refresh(
    *,
    db: Session,
    users_controller: Any,
    refresh_token: str,
) -> Tuple[str, Any]:
    """
    Panggil controller untuk validasi refresh_token dan menghasilkan access_token baru.
    """
    # ekspektasi: users_controller.refresh_access_token(db, refresh_token) -> (new_access_token, user_nid)
    return await users_controller.refresh_access_token(db=db, refresh_token=refresh_token)
