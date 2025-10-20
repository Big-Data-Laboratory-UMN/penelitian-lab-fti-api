from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import timedelta
from ..controller import userAccessController
from ..schemas import usersSchema as schema
from ..controller import usersController
from ..database import SessionLocal

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


@router.post("/token", response_model=schema.TokenResponse)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    print(f"Login attempt received for username: {form_data.username}")
    try:
        user = usersController.authenticate_user(db, email=form_data.username, password=form_data.password)
        if not user:
            print(f"Login failed for {form_data.username}: Invalid credentials.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email atau password salah",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token_expires = timedelta(minutes=usersController.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(days=usersController.REFRESH_TOKEN_EXPIRE_MINUTES)

        access_token = usersController.create_access_token(
            data={"sub": str(user.nid)}, expires_delta=access_token_expires
        )
        refresh_token = usersController.create_refresh_token(
            data={"sub": str(user.nid)}, expires_delta=refresh_token_expires
        )

        print(f"Token generated successfully for user {user.vemail} (ID: {user.nid})")
        user_response = schema.User.model_validate(user)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token, # Kembalikan refresh token juga
            "token_type": "bearer",
            "user": user_response
        }
    except ValueError as e:
         print(f"Login failed for {form_data.username}: {str(e)}")
         raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    except Exception as e:
        print(f"Unexpected error during login for {form_data.username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Terjadi kesalahan pada server saat mencoba login."
        )

@router.post("/refresh_token", response_model=schema.NewAccessTokenResponse)
async def refresh_token(refresh_request: schema.RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        new_access_token = usersController.refresh_access_token(db=db, refresh_token=refresh_request.refresh_token)
        return {"access_token": new_access_token, "token_type": "bearer"}
    except HTTPException as e:
        # Re-raise HTTPException from controller (like 401 if refresh token is bad)
        raise e
    except Exception as e:
        print(f"Unexpected error during token refresh: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal memperbarui token."
        )

@router.get("/me", response_model=schema.User)
async def read_users_me(current_user: schema.User = Depends(usersController.get_current_active_user)):
    return current_user

@router.post("/admin-create", response_model=schema.User, status_code=status.HTTP_201_CREATED)
async def create_user_from_admin_panel(user: schema.UserCreateByAdmin, request: Request, db: Session = Depends(get_db), current_user: schema.User = Depends(usersController.get_current_active_user)):
    
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)

    if "PIC" in user_roles or "VSTR" in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk melihat data ini."
        )
    
    try:
        new_user = await usersController.create_user_by_admin(
            db=db,
            user_data=user,
            app=request.app,
            db_factory=SessionLocal
        )
        return new_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/set-initial-password", response_model=schema.User)
def set_user_initial_password(password_data: schema.SetInitialPassword, db: Session = Depends(get_db)):
    try:
        updated_user = usersController.set_initial_password(db=db, password_data=password_data)
        return updated_user
    except ValueError as e:
        if "Invalid" in str(e) or "expired" in str(e) or "used" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/resend-activation/{user_vcode}", status_code=status.HTTP_200_OK)
async def resend_user_activation(user_vcode: str, request: Request, db: Session = Depends(get_db)):
    try:
        response_message = await usersController.resend_activation_email(
            db=db,
            user_vcode=user_vcode,
            app=request.app,
            db_factory=SessionLocal
        )
        return response_message
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resend email: {str(e)}")

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
    current_user: schema.User = Depends(usersController.get_current_active_user)
):
    
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)

    if "PIC" in user_roles or "VSTR" in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk melihat data ini."
        )
    
    users_data = usersController.get_users(
        db=db, skip=skip, limit=limit, search=search,
        nstatus=nstatus, vname=name, vemail=email, vcode=code
    )
    return users_data

@router.get("/{user_id}", response_model=schema.User)
def get_user_by_id(user_id: int, db: Session = Depends(get_db), current_user: schema.User = Depends(usersController.get_current_active_user)):
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)

    if "PIC" in user_roles or "VSTR" in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk melihat data ini."
        )
        
    user = usersController.get_user(db=db, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_vcode}", response_model=schema.User)
async def update_existing_user(user_vcode: str, user: schema.UserUpdate, request: Request, db: Session = Depends(get_db), current_user: schema.User = Depends(usersController.get_current_active_user)):
    try:
        db_user = await usersController.update_user(
            db=db,
            user_vcode=user_vcode,
            user=user,
            app=request.app,
            db_factory=SessionLocal
        )
        
        user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)

        if "PIC" in user_roles or "VSTR" in user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Anda tidak punya hak akses untuk melihat data ini."
            )
        
        if db_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return db_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{user_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_user(user_vcode: str, db: Session = Depends(get_db), current_user: schema.User = Depends(usersController.get_current_active_user)):
    
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)

    if "PIC" in user_roles or "VSTR" in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk melihat data ini."
        )
    
    user = usersController.delete_user(db=db, user_vcode=user_vcode)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return

@router.get("/validate-activation-token/{token}")
def validate_activation_token(token: str, db: Session = Depends(get_db)):
    result = usersController.verify_activation_token(db=db, token=token)
    if not result["valid"]:
        raise HTTPException(status_code=404, detail=result["reason"])
    return result

@router.get("/verify-email-change/{token}", response_model=schema.User)
def verify_user_email_change(token: str, db: Session = Depends(get_db)):
    try:
        updated_user = usersController.verify_and_update_email(db=db, token=token)
        return updated_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/all-for-dropdown/", response_model=schema.UserDropdownResponse)
def read_all_users_for_dropdown(db: Session = Depends(get_db), current_user: schema.User = Depends(usersController.get_current_active_user)):
    
    user_roles = userAccessController.get_user_roles_by_user_id(db=db, user_id=current_user.nid)

    if "PIC" in user_roles or "VSTR" in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anda tidak punya hak akses untuk melihat data ini."
        )
    users_data = usersController.get_all_users_for_dropdown(db=db)
    return users_data