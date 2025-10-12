import os
import secrets
from datetime import datetime, timedelta
import pytz

from fastapi_apscheduler import scheduler # type: ignore
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext  # type: ignore

from ..models import usersModel as models
from ..models import tokenModel
from ..schemas import usersSchema as schema
from utils.email_service import send_activation_email

jakarta_tz = pytz.timezone("Asia/Jakarta")

PASSWORD_PEPPER = os.getenv("PASSWORD_PEPPER")
if not PASSWORD_PEPPER:
    raise ValueError("CRITICAL: PASSWORD_PEPPER not found in environment variables.")

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


# ======================
# PASSWORD UTILS
# ======================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_with_pepper = plain_password + PASSWORD_PEPPER
    return pwd_context.verify(password_with_pepper, hashed_password)


def get_password_hash(password: str) -> str:
    password_with_pepper = password + PASSWORD_PEPPER
    return pwd_context.hash(password_with_pepper)


# ======================
# MAIN USER FUNCTIONS
# ======================

async def create_user_by_admin(db: Session, user_data: schema.UserCreateByAdmin, app=None, db_factory=None):
    """Admin create user -> send activation email -> start personal countdown."""
    db_user = models.User(**user_data.model_dump(), vpassword=None, nstatus=2)
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        activation_token_str = secrets.token_urlsafe(32)
        expires_at = datetime.now(jakarta_tz) + timedelta(minutes=1)

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

        # Kirim email aktivasi
        try:
            await send_activation_email(
                recipient_email=db_user.vemail,
                user_name=db_user.vname,
                activation_token=activation_token_str,
            )
        except Exception as e:
            print(f"ERROR: User {db_user.vemail} created, BUT failed to send activation email. Error: {e}")

        # Jadwalkan auto-expire untuk user ini
        if app and hasattr(app.state, "scheduler") and db_factory:
            schedule_user_expiry(
                sched=app.state.scheduler,
                db_factory=db_factory,
                user_id=db_user.nid,
                token_id=db_token.nid,
                expires_at=expires_at
            )

        print(f"✅ User {db_user.vemail} created, activation email sent, expiry in 60s.")
        return db_user

    except IntegrityError:
        db.rollback()
        raise ValueError("Failed to save. The provided user code or email is already in use.")


def set_initial_password(db: Session, password_data: schema.SetInitialPassword):
    db_token = db.query(tokenModel.Token).filter(
        tokenModel.Token.vcode == password_data.token,
        tokenModel.Token.ntoken_type == 1
    ).first()

    if not db_token:
        raise ValueError("Invalid or expired activation token.")
    if db_token.nstatus == 0:
        raise ValueError("This activation link has already been used.")

    if db_token.dexpires_at < datetime.now(jakarta_tz):
        user_to_update = db.query(models.User).filter(models.User.nid == db_token.nid_user).first()
        if user_to_update:
            user_to_update.nstatus = 3
            db_token.nstatus = 0
            db.commit()
        raise ValueError("Activation link has expired. Please request a new one.")

    user = db.query(models.User).filter(models.User.nid == db_token.nid_user).first()
    if not user:
        raise ValueError("User associated with this token not found.")

    user.vpassword = get_password_hash(password_data.password)
    user.nstatus = 1
    db_token.nstatus = 0

    db.commit()
    db.refresh(user)
    return user


async def resend_activation_email(db: Session, user_vcode: str, app=None, db_factory=None):
    user = get_user_by_code(db, user_code=user_vcode)
    if not user:
        raise ValueError("User not found.")

    activation_token_str = secrets.token_urlsafe(32)
    expires_at = datetime.now(jakarta_tz) + timedelta(minutes=1)

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

    db.commit()
    db.refresh(db_token)

    await send_activation_email(
        recipient_email=user.vemail,
        user_name=user.vname,
        activation_token=activation_token_str,
    )

    # Jadwalkan countdown baru juga
    if app and hasattr(app.state, "scheduler") and db_factory:
        schedule_user_expiry(
            sched=app.state.scheduler,
            db_factory=db_factory,
            user_id=user.nid,
            token_id=db_token.nid,
            expires_at=expires_at
        )

    print(f"🔁 Resent activation email to {user.vemail}, expiry in 24 hours.")
    return {"message": "Activation email has been resent successfully."}


# ======================
# PER-USER EXPIRY SCHEDULER
# ======================

def schedule_user_expiry(sched, db_factory, user_id: int, token_id: int, expires_at: datetime):
    """
    Jadwalkan auto-expire untuk satu user tertentu (fixed 24 jam), 
    dengan countdown real-time (debug).
    """
    import threading, sys, time

    # Logika diubah: parameter 'expires_at' diabaikan.
    # Waktu expire sekarang di-set fix 24 jam dari sekarang.
    delay = 24 * 60 * 60  # 24 jam dalam detik
    # delay = 60 # 1 menit untuk testing

    # Menggunakan waktu sekarang ditambah delay 24 jam untuk menentukan waktu eksekusi
    now = datetime.now(jakarta_tz)
    run_time = now + timedelta(seconds=delay)

    @sched.scheduled_job("date", run_date=run_time)
    def expire_single_user():
        db = db_factory()
        try:
            user = db.query(models.User).filter(models.User.nid == user_id).first()
            token = db.query(tokenModel.Token).filter(tokenModel.Token.nid == token_id).first()
            
            # Cek jika user masih dalam status menunggu aktivasi (nstatus == 2)
            if user and user.nstatus == 2:
                user.nstatus = 3  # Set status ke expired
                user.vmodified_by = "system"
                if token:
                    token.nstatus = 0 # Non-aktifkan token
                db.commit()
                sys.stdout.write(f"\n[EXPIRE] User {user.vemail} otomatis expired setelah 24 jam.\n")
                sys.stdout.flush()
            else:
                print(f"[SKIP] User {user_id} sudah diaktivasi atau status berubah sebelum 24 jam.")
        finally:
            db.close()

    # Debug countdown in real-time (works on Windows & Unix)
    def countdown_display():
        total = int(delay)
        while total > 0:
            # Konversi total detik ke format HH:MM:SS
            mins, secs = divmod(total, 60)
            hours, mins = divmod(mins, 60)
            time_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
            
            sys.stdout.write(f"\r[COUNTDOWN] UserID={user_id} | expires in {time_str} ")
            sys.stdout.flush()
            time.sleep(1)
            total -= 1
        sys.stdout.write(f"\r[COUNTDOWN] UserID={user_id} pemicu ekspirasi 24 jam tercapai.{' ' * 20}\n")
        sys.stdout.flush()

    # Jalankan countdown di thread terpisah agar tidak memblokir proses utama
    t = threading.Thread(target=countdown_display, daemon=True)
    t.start()


# ======================
# GLOBAL SCHEDULER INIT
# ======================

def start_scheduler(app):
    sched = scheduler.AsyncIOScheduler()
    sched.start()
    app.state.scheduler = sched
    print("✅ Scheduler started and ready for dynamic per-user jobs.")


# ======================
# CRUD HELPERS
# ======================

def get_user_by_code(db: Session, user_code: str):
    return db.query(models.User).filter(models.User.vcode == user_code).first()


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.vemail == email).first()


def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.nid == user_id).first()


def update_user(db: Session, user_vcode: str, user: schema.UserUpdate):
    db_user = get_user_by_code(db, user_code=user_vcode)
    if not db_user:
        return None

    update_data = user.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_user, key, value)

    try:
        db.commit()
        db.refresh(db_user)
        return db_user
    except IntegrityError:
        db.rollback()
        raise ValueError("Failed to update. The provided user code or email is already in use.")


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
        db_user.nstatus = 0
        db_user.vmodified_by = "system"
        db.commit()
        db.refresh(db_user)
    return db_user


def get_all_users_for_dropdown(db: Session):
    users = db.query(models.User).filter(models.User.nstatus == 1).order_by(models.User.vname).all()
    return {"data": users}
