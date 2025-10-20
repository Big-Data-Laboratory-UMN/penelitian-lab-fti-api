import os
import secrets
from datetime import datetime, timedelta
import pytz
import threading
import sys
import time

from fastapi import Depends, HTTPException, status
from fastapi_apscheduler import scheduler
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer

from ..models import usersModel as models
from ..models import tokenModel
from ..schemas import usersSchema as schema
from utils.email_service import send_activation_email, send_email_change_verification_email
from ..database import SessionLocal

jakarta_tz = pytz.timezone("Asia/Jakarta")

PASSWORD_PEPPER = os.getenv("PASSWORD_PEPPER")
if not PASSWORD_PEPPER:
    raise ValueError("CRITICAL: PASSWORD_PEPPER not found in environment variables.")

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1"))
REFRESH_TOKEN_EXPIRE_MINUTES = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "3"))# Default 30 hari

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/token")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    # Optionally add a claim to distinguish refresh tokens if needed, e.g., to_encode["type"] = "refresh"
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def create_user_by_admin(db: Session, user_data: schema.UserCreateByAdmin, app=None, db_factory=None):
    db_user = models.User(**user_data.model_dump(), vpassword=None, nstatus=2)
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        activation_token_str = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=24)

        db_token = tokenModel.Token(
            nid_user=db_user.nid,
            ntoken_type=1,
            vcode=activation_token_str,
            dexpires_at=expires_at,
            nstatus=1
        )
        db.add(db_token)
        db.commit()
        db.refresh(db_token)

        try:
            await send_activation_email(
                recipient_email=db_user.vemail,
                user_name=db_user.vname,
                activation_token=activation_token_str,
            )
        except Exception as e:
            print(f"ERROR: User {db_user.vemail} created, BUT failed to send activation email. Error: {e}")

        if app and hasattr(app.state, "scheduler") and db_factory:
            schedule_token_expiry(
                sched=app.state.scheduler,
                db_factory=db_factory,
                user_id=db_user.nid,
                token_id=db_token.nid,
                task_type='user_activation'
            )

        print(f"✅ User {db_user.vemail} created, activation email sent, expiry in 24h.")
        return db_user

    except IntegrityError:
        db.rollback()
        raise ValueError("Failed to save. The provided NIM/NIK or email is already in use.")

def authenticate_user(db: Session, email: str, password: str) -> models.User | None:
    user = get_user_by_email(db, email=email)

    if not user:
        print(f"Login attempt failed: Email '{email}' not found.")
        return None

    if user.nstatus == 0:
        print(f"Login attempt failed: User '{email}' is inactive.")
        raise ValueError("Akun Anda tidak aktif.")
    if user.nstatus == 2:
        print(f"Login attempt failed: User '{email}' is pending activation.")
        raise ValueError("Akun Anda belum diaktivasi. Silakan cek email Anda.")
    if user.nstatus == 3:
        print(f"Login attempt failed: User '{email}' activation expired.")
        raise ValueError("Aktivasi akun Anda sudah kedaluwarsa. Silakan minta kirim ulang email aktivasi.")
    if not user.vpassword:
         print(f"Login attempt failed: User '{email}' has no password set (likely created by admin).")
         raise ValueError("Password belum diatur. Silakan gunakan link aktivasi di email Anda.")

    if user.nstatus == 1 and user.vpassword:
        if not verify_password(password, user.vpassword):
            print(f"Login attempt failed: Invalid password for user '{email}'.")
            return None
    else:
        print(f"Login attempt failed: User '{email}' has invalid status ({user.nstatus}) or no password for verification.")
        return None

    print(f"Login attempt successful for user '{email}'.")
    return user

def refresh_access_token(db: Session, refresh_token: str):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
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
    if user is None or user.nstatus != 1:
        raise credentials_exception

    # Create a new access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_access_token(
        data={"sub": str(user.nid)}, expires_delta=access_token_expires
    )
    return new_access_token

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        user_nid = int(user_id)
    except (JWTError, ValueError):
        raise credentials_exception

    user = get_user(db, user_id=user_nid)
    if user is None:
        raise credentials_exception

    if user.nstatus != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return user

async def get_current_active_user(current_user: schema.User = Depends(get_current_user)):
    if current_user.nstatus != 1:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def update_user(db: Session, user_vcode: str, user: schema.UserUpdate, app=None, db_factory=None):
    db_user = get_user_by_code(db, user_code=user_vcode)
    if not db_user:
        return None

    db_user.vmodified_by = user.vmodified_by or 'system'
    update_data = user.model_dump(exclude_unset=True)

    if 'vemail' in update_data and update_data['vemail'] != db_user.vemail:
        new_email = update_data.pop('vemail')
        verification_token_str = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=24)

        db_token = tokenModel.Token(
            nid_user=db_user.nid,
            ntoken_type=4,
            vcode=verification_token_str,
            vnew_email=new_email,
            dexpires_at=expires_at,
            nstatus=1
        )
        db.add(db_token)

        try:
            db.commit()
            db.refresh(db_token)
        except IntegrityError:
            db.rollback()
            raise ValueError("Failed to initiate email change. The new email might already be pending verification.")

        await send_email_change_verification_email(
            recipient_email=new_email,
            user_name=db_user.vname,
            verification_token=verification_token_str,
        )

        if app and hasattr(app.state, "scheduler") and db_factory:
            schedule_token_expiry(
                sched=app.state.scheduler,
                db_factory=db_factory,
                user_id=db_user.nid,
                token_id=db_token.nid,
                task_type='email_change'
            )

        print(f"📧 Verification email sent to {new_email} for user {db_user.vcode}. Expires in 24 hours.")


    for key, value in update_data.items():
        setattr(db_user, key, value)

    try:
        db_user.dsort_at = datetime.utcnow()
        db.commit()
        db.refresh(db_user)
        return db_user
    except IntegrityError:
        db.rollback()
        raise ValueError("Failed to update user. The provided user NIM/NIK or another unique field might already be in use.")


async def resend_activation_email(db: Session, user_vcode: str, app=None, db_factory=None):
    user = get_user_by_code(db, user_code=user_vcode)
    if not user:
        raise ValueError("User not found.")
    if user.nstatus not in [2, 3]:
        raise ValueError(f"User is already {user.nstatus}, cannot resend activation.")

    activation_token_str = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=24)

    db_token = tokenModel.Token(
        nid_user=user.nid,
        ntoken_type=1,
        vcode=activation_token_str,
        dexpires_at=expires_at,
        nstatus=1
    )
    db.add(db_token)

    if user.nstatus == 3:
        user.nstatus = 2
        user.vmodified_by = "system"
        user.dsort_at = datetime.utcnow()

    db.commit()
    db.refresh(db_token)

    await send_activation_email(
        recipient_email=user.vemail,
        user_name=user.vname,
        activation_token=activation_token_str,
    )

    if app and hasattr(app.state, "scheduler") and db_factory:
        schedule_token_expiry(
            sched=app.state.scheduler,
            db_factory=db_factory,
            user_id=user.nid,
            token_id=db_token.nid,
            task_type='user_activation'
        )

    print(f"🔁 Resent activation email to {user.vemail}, expiry in 24 hours.")
    return {"message": "Activation email has been resent successfully."}


def schedule_token_expiry(sched, db_factory, user_id: int, token_id: int, task_type: str):
    delay_seconds = 24 * 60 * 60

    job_id = f"{task_type}_{token_id}"

    if sched.get_job(job_id):
        sched.remove_job(job_id)
        print(f"[SCHEDULER] Removed existing job: {job_id}")

    run_time = datetime.now(jakarta_tz) + timedelta(seconds=delay_seconds)

    @sched.scheduled_job("date", run_date=run_time, id=job_id)
    def expire_token_job():
        db = db_factory()
        try:
            token = db.query(tokenModel.Token).filter(tokenModel.Token.nid == token_id).first()
            if not token or token.nstatus != 1:
                sys.stdout.write(f"\n[SKIP] Job {job_id} skipped, token already used or invalid.\n")
                sys.stdout.flush()
                return

            if task_type == 'user_activation':
                user = db.query(models.User).filter(models.User.nid == user_id).first()
                if user and user.nstatus == 2:
                    user.nstatus = 3
                    user.vmodified_by = "system-scheduler"
                    user.dsort_at = datetime.utcnow()
                    token.nstatus = 0
                    db.commit()
                    sys.stdout.write(f"\n[EXPIRE] User activation for {user.vemail} (ID: {user_id}) has expired.\n")
                    sys.stdout.flush()

            elif task_type == 'email_change':
                token.nstatus = 0
                db.commit()
                sys.stdout.write(f"\n[EXPIRE] Email change token for UserID={user_id} has expired.\n")
                sys.stdout.flush()

        finally:
            db.close()

    def countdown_display():
        total = int(delay_seconds)

        while total > 0:
            try:
                if total % 15 == 0:
                    db_check = db_factory()
                    token = db_check.query(tokenModel.Token).filter(tokenModel.Token.nid == token_id).first()
                    if not token or token.nstatus != 1:
                        sys.stdout.write(f"\r[COUNTDOWN] Job {job_id} stopped, token has been processed.{' ' * 20}\n")
                        sys.stdout.flush()
                        return
                    db_check.close()
            except Exception as e:
                print(f"Error checking token status in countdown: {e}")

            mins, secs = divmod(total, 60)
            hours, mins = divmod(mins, 60)
            time_str = f"{hours:02d}:{mins:02d}:{secs:02d}"

            sys.stdout.write(f"\r[COUNTDOWN] Job {job_id} will trigger in {time_str} ")
            sys.stdout.flush()
            time.sleep(1)
            total -= 1

        sys.stdout.write(f"\r[COUNTDOWN] Job {job_id} trigger time reached.{' ' * 40}\n")
        sys.stdout.flush()

    print(f"[SCHEDULER] Job '{job_id}' scheduled to run at {run_time.strftime('%Y-%m-%d %H:%M:%S')}")


def verify_and_update_email(db: Session, token: str):
    db_token = db.query(tokenModel.Token).filter(
        tokenModel.Token.vcode == token,
        tokenModel.Token.ntoken_type == 4
    ).first()

    if not db_token:
        raise ValueError("Token verifikasi tidak valid atau tidak ditemukan.")
    if db_token.nstatus == 0:
        raise ValueError("Tautan verifikasi ini sudah pernah digunakan.")
    if db_token.dexpires_at < datetime.utcnow():
        db_token.nstatus = 0
        db.commit()
        raise ValueError("Tautan verifikasi sudah kedaluwarsa.")

    user_to_update = db.query(models.User).filter(models.User.nid == db_token.nid_user).first()
    if not user_to_update:
        raise ValueError("User yang terkait dengan token ini tidak ditemukan.")

    existing_user_with_new_email = db.query(models.User).filter(models.User.vemail == db_token.vnew_email, models.User.nid != user_to_update.nid).first()
    if existing_user_with_new_email:
         raise ValueError("Gagal memperbarui. Alamat email baru sudah digunakan oleh user lain.")

    user_to_update.vemail = db_token.vnew_email
    user_to_update.vmodified_by = "system"
    user_to_update.dsort_at = datetime.utcnow()
    db_token.nstatus = 0
    db_token.vnew_email = None

    try:
        db.commit()
        db.refresh(user_to_update)
        print(f"✅ Email for user {user_to_update.vcode} successfully updated to {user_to_update.vemail}.")
        return user_to_update
    except IntegrityError:
        db.rollback()
        raise ValueError("Gagal memperbarui. Alamat email baru mungkin sudah digunakan oleh user lain.")


def set_initial_password(db: Session, password_data: schema.SetInitialPassword):
    db_token = db.query(tokenModel.Token).filter(
        tokenModel.Token.vcode == password_data.token,
        tokenModel.Token.ntoken_type == 1
    ).first()

    if not db_token:
        raise ValueError("Invalid or expired activation token.")
    if db_token.nstatus == 0:
        raise ValueError("This activation link has already been used.")

    if db_token.dexpires_at < datetime.utcnow():
        user_to_update = db.query(models.User).filter(models.User.nid == db_token.nid_user).first()
        if user_to_update and user_to_update.nstatus == 2:
            user_to_update.nstatus = 3
            user_to_update.vmodified_by = "system"
            user_to_update.dsort_at = datetime.utcnow()
            db_token.nstatus = 0
            db.commit()
        raise ValueError("Activation link has expired. Please request a new one.")

    user = db.query(models.User).filter(models.User.nid == db_token.nid_user).first()
    if not user:
        raise ValueError("User associated with this token not found.")

    if user.nstatus != 2:
        raise ValueError("This activation link cannot be used for this account status.")


    user.vpassword = get_password_hash(password_data.password)
    user.nstatus = 1
    user.vmodified_by = "system-activation"
    user.dsort_at = datetime.utcnow()
    db_token.nstatus = 0

    db.commit()
    db.refresh(user)

    print(f"✅ Password for user {user.vemail} (ID: {user.nid}) has been successfully set.")
    print(f"   -> User status is now ACTIVE. Any running expiration countdown for this user is now void and will be skipped.")

    return user


def start_scheduler(app):
    sched = scheduler.AsyncIOScheduler()
    try:
      sched.start()
      app.state.scheduler = sched
      print("✅ Scheduler started and ready for dynamic per-user jobs.")
    except Exception as e:
      print(f"❌ Failed to start scheduler: {e}")


def get_user_by_code(db: Session, user_code: str):
    return db.query(models.User).filter(models.User.vcode == user_code).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.vemail == email).first()

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.nid == user_id).first()

def get_users(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    nstatus: int | None = None,
    vname: str | None = None,
    vemail: str | None = None,
    vcode: str | None = None,
):
    query = db.query(models.User)
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
        query = query.filter(models.User.nstatus == nstatus)

    total = query.count()
    query = query.order_by(models.User.dsort_at.desc())
    data = query.offset(skip).limit(limit).all()
    return {"data": data, "total": total}

def delete_user(db: Session, user_vcode: str):
    db_user = get_user_by_code(db, user_code=user_vcode)
    if db_user:
        if db_user.nstatus == 0:
            return db_user
        db_user.nstatus = 0
        db_user.vmodified_by = "system"
        db_user.dsort_at = datetime.utcnow()
        db.commit()
        db.refresh(db_user)
    return db_user

def get_all_users_for_dropdown(db: Session):
    users = db.query(models.User).filter(models.User.nstatus == 1).order_by(models.User.vname).all()
    return {"data": users}

def verify_activation_token(db: Session, token: str):
    db_token = (
        db.query(tokenModel.Token)
        .filter(
            tokenModel.Token.vcode == token,
            tokenModel.Token.ntoken_type == 1
        )
        .first()
    )

    if not db_token:
        return {"valid": False, "reason": "Token not found."}
    if db_token.nstatus == 0:
        return {"valid": False, "reason": "Token already used or deactivated."}

    if db_token.dexpires_at < datetime.utcnow():
        user_to_update = db.query(models.User).filter(models.User.nid == db_token.nid_user).first()
        if user_to_update and user_to_update.nstatus == 2:
            user_to_update.nstatus = 3
            user_to_update.vmodified_by = "system-token-verify"
            user_to_update.dsort_at = datetime.utcnow()
            db_token.nstatus = 0
            db.commit()
        return {"valid": False, "reason": "Token expired."}

    user = db.query(models.User).filter(models.User.nid == db_token.nid_user).first()
    if not user:
        db_token.nstatus = 0
        db.commit()
        return {"valid": False, "reason": "Associated user not found."}

    if user.nstatus != 2:
        db_token.nstatus = 0
        db.commit()
        if user.nstatus == 1:
             return {"valid": False, "reason": "User already active."}
        elif user.nstatus == 3:
             return {"valid": False, "reason": "User activation expired."}
        else:
             return {"valid": False, "reason": f"User status is not valid for activation ({user.nstatus})."}


    return {"valid": True, "reason": "Token is active and valid."}

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    password_with_pepper = plain_password + PASSWORD_PEPPER
    try:
      return pwd_context.verify(password_with_pepper, hashed_password)
    except Exception as e:
      print(f"Error verifying password: {e}")
      return False


def get_password_hash(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty")
    password_with_pepper = password + PASSWORD_PEPPER
    return pwd_context.hash(password_with_pepper)