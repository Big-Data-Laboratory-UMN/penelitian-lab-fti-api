from fastapi import APIRouter, Depends, HTTPException, status, Request  # type: ignore
from sqlalchemy.orm import Session
from typing import List, Optional

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

@router.post("/admin-create", response_model=schema.User, status_code=status.HTTP_201_CREATED)
async def create_user_from_admin_panel(user: schema.UserCreateByAdmin, request: Request, db: Session = Depends(get_db)):
    """
    Endpoint untuk Admin membuat user baru.
    Akan memicu pengiriman email aktivasi.
    """
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
    """
    Endpoint untuk user mengatur password pertamanya setelah klik link di email.
    """
    try:
        updated_user = usersController.set_initial_password(db=db, password_data=password_data)
        return updated_user
    except ValueError as e:
        if "Invalid" in str(e) or "expired" in str(e) or "used" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/resend-activation/{user_vcode}", status_code=status.HTTP_200_OK)
async def resend_user_activation(user_vcode: str, request: Request, db: Session = Depends(get_db)):
    """
    Endpoint untuk mengirim ulang email aktivasi ke user.
    """
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
    db: Session = Depends(get_db)
):
    users_data = usersController.get_users(
        db=db, skip=skip, limit=limit, search=search, 
        nstatus=nstatus, vname=name, vemail=email, vcode=code
    )
    return users_data

@router.get("/{user_id}", response_model=schema.User)
def get_user_by_id(user_id: int, db: Session = Depends(get_db)):
    user = usersController.get_user(db=db, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/{user_vcode}", response_model=schema.User)
async def update_existing_user(user_vcode: str, user: schema.UserUpdate, request: Request, db: Session = Depends(get_db)):
    try:
        db_user = await usersController.update_user(
            db=db, 
            user_vcode=user_vcode, 
            user=user,
            app=request.app,
            db_factory=SessionLocal 
        )
        if db_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return db_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{user_vcode}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_user(user_vcode: str, db: Session = Depends(get_db)):
    user = usersController.delete_user(db=db, user_vcode=user_vcode)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return

@router.get("/validate-token/{token}")
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
def read_all_roles_permissions_for_dropdown(db: Session = Depends(get_db)):
    users_data = usersController.get_all_users_for_dropdown(db=db)
    return users_data
