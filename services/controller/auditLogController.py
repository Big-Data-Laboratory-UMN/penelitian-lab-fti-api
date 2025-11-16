from sqlalchemy.orm import Session
from fastapi import Request
from datetime import datetime
import pytz

# Import model baru lu
from ..models import securityLogModel, activityLogModel

# Import schema user buat type hinting
from ..schemas import usersSchema

# Ambil SessionLocal buat background task
from ..database import SessionLocal 

# Copy/paste
def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))

# =========================================
# FUNGSI UNTUK SECURITY LOG (tblh_security_logs)
# =========================================

def create_security_log(
    db: Session,
    nid_user: int | None,
    action: str,
    request: Request | None = None, # Buat ambil IP & User-Agent
    details: str | None = None
):
    """
    Nulis log ke tabel security. 
    Fungsi ini GAK Boleh db.commit()
    """
    vip = request.client.host if request else None
    user_agent = request.headers.get("user-agent") if request else None
    
    db_log = securityLogModel.SecurityLog(
        nid_user=nid_user,
        vaction=action,
        vip_address=vip,
        vuser_agent=user_agent,
        vdetails=details,
        dtimestamp=now_wib()
    )
    db.add(db_log)
    
    # PENTING: JANGAN db.commit() di sini.
    # Kita "numpang" commit dari fungsi yang manggil (misal: pas login, pas reset password, dll)

# =========================================
# FUNGSI UNTUK ACTIVITY LOG (tblh_activity_logs)
# =========================================

def create_activity_log_task(
    nid_user: int,
    action: str,
    target_model: str,
    target_identifier: str,
    jbefore: dict | None,
    jafter: dict | None,
    ip: str | None,
    user_agent: str | None
):
    """
    Nulis log ke tabel activity. 
    Fungsi ini HARUS Bikin Session & Commit sendiri.
    (Karena bakal dijalanin di Background Task)
    """
    db: Session = SessionLocal() # Bikin session DB baru khusus buat task ini
    try:
        db_log = activityLogModel.ActivityLog(
            nid_user=nid_user,
            vaction=action,
            vtarget_model=target_model,
            vtarget_identifier=str(target_identifier), # Pastiin string
            jbefore=jbefore,
            jafter=jafter,
            vip_address=ip,
            vuser_agent=user_agent,
            dtimestamp=now_wib()
        )
        db.add(db_log)
        db.commit() # Commit di sini
        print(f"[AUDIT LOG] Success: {action} on {target_model} (ID: {target_identifier}) by user {nid_user}")
    except Exception as e:
        print(f"[AUDIT LOG ERROR] Gagal nyimpen activity log: {e}")
        db.rollback()
    finally:
        db.close() # Wajib di-close