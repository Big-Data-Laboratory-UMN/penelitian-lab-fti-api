from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func, or_
from fastapi import Request, HTTPException, status # Tambah HTTPException
from datetime import datetime, date, timedelta
import pytz
from typing import Optional

# Import models
from ..models import securityLogModel, activityLogModel, usersModel

# Import database session buat background task
from ..database import SessionLocal 

def now_wib():
    return datetime.now(pytz.timezone("Asia/Jakarta"))


def create_security_log(db: Session, nid_user: int | None, action: str, request: Request | None = None, details: str | None = None):
    vip = request.client.host if request else None
    user_agent = request.headers.get("user-agent") if request else None
    db_log = securityLogModel.SecurityLog(nid_user=nid_user, vaction=action, vip_address=vip, vuser_agent=user_agent, vdetails=details, dtimestamp=now_wib())
    db.add(db_log)

def create_activity_log_task(nid_user: int, action: str, target_model: str, target_identifier: str, jbefore: dict | None, jafter: dict | None, ip: str | None, user_agent: str | None):
    db: Session = SessionLocal()
    try:
        db_log = activityLogModel.ActivityLog(nid_user=nid_user, vaction=action, vtarget_model=target_model, vtarget_identifier=str(target_identifier), jbefore=jbefore, jafter=jafter, vip_address=ip, vuser_agent=user_agent, dtimestamp=now_wib())
        db.add(db_log)
        db.commit()
    except Exception as e:
        print(f"[AUDIT LOG ERROR] Gagal nyimpen activity log: {e}")
        db.rollback()
    finally:
        db.close()


def get_activity_log_by_id(db: Session, log_id: int):
    """
    Ambil 1 detail Activity Log berdasarkan Primary Key (nid).
    """
    log = db.query(activityLogModel.ActivityLog).options(
        joinedload(activityLogModel.ActivityLog.user) # Eager load user biar efisien
    ).filter(activityLogModel.ActivityLog.nid == log_id).first()

    if not log:
        raise HTTPException(status_code=404, detail="Activity Log not found")

    # Manual formatting biar sesuai schema Response
    user_obj = log.user
    role_name = "Unknown"
    if user_obj and hasattr(user_obj, 'user_access_rel') and user_obj.user_access_rel:
            active_access = next((ua for ua in user_obj.user_access_rel if ua.nstatus == 1), None)
            if active_access and active_access.role:
                role_name = active_access.role.vname

    return {
        "nid": log.nid,
        "actor_name": user_obj.vname if user_obj else "System",
        "actor_email": user_obj.vemail if user_obj else "system@app",
        "actor_role": role_name,
        "vaction": log.vaction,
        "vtarget_model": log.vtarget_model,
        "vtarget_identifier": log.vtarget_identifier,
        "jbefore": log.jbefore,
        "jafter": log.jafter,
        "vip_address": log.vip_address,
        "dtimestamp": log.dtimestamp
    }

def get_security_log_by_id(db: Session, log_id: int):
    """
    Ambil 1 detail Security Log berdasarkan Primary Key (nid).
    """
    log = db.query(securityLogModel.SecurityLog).options(
        joinedload(securityLogModel.SecurityLog.user)
    ).filter(securityLogModel.SecurityLog.nid == log_id).first()

    if not log:
        raise HTTPException(status_code=404, detail="Security Log not found")

    return {
        "nid": log.nid,
        "actor_name": log.user.vname if log.user else "Guest/System",
        "actor_email": log.user.vemail if log.user else None,
        "vaction": log.vaction,
        "vip_address": log.vip_address,
        "vuser_agent": log.vuser_agent,
        "vdetails": log.vdetails,
        "dtimestamp": log.dtimestamp
    }

def get_activity_logs(db: Session, page: int = 1, limit: int = 10, search: Optional[str] = None, module: Optional[str] = None, action: Optional[str] = None, start_date: Optional[date] = None, end_date: Optional[date] = None):
    query = db.query(activityLogModel.ActivityLog).outerjoin(usersModel.User, activityLogModel.ActivityLog.nid_user == usersModel.User.nid)

    if search:
        search_fmt = f"%{search}%"
        query = query.filter(or_(usersModel.User.vname.ilike(search_fmt), activityLogModel.ActivityLog.vtarget_identifier.ilike(search_fmt), activityLogModel.ActivityLog.vaction.ilike(search_fmt), activityLogModel.ActivityLog.vtarget_model.ilike(search_fmt)))
    
    if module: query = query.filter(activityLogModel.ActivityLog.vtarget_model == module)
    if action: query = query.filter(activityLogModel.ActivityLog.vaction == action)
    if start_date: query = query.filter(func.date(activityLogModel.ActivityLog.dtimestamp) >= start_date)
    if end_date: query = query.filter(func.date(activityLogModel.ActivityLog.dtimestamp) <= end_date)

    total = query.count()
    logs = query.order_by(desc(activityLogModel.ActivityLog.dtimestamp)).offset((page - 1) * limit).limit(limit).all()

    results = []
    for log in logs:
        user_obj = log.user
        role_name = "Unknown"
        if user_obj and hasattr(user_obj, 'user_access_rel') and user_obj.user_access_rel:
             active_access = next((ua for ua in user_obj.user_access_rel if ua.nstatus == 1), None)
             if active_access and active_access.role:
                 role_name = active_access.role.vname

        results.append({
            "nid": log.nid,
            "actor_name": user_obj.vname if user_obj else "System",
            "actor_email": user_obj.vemail if user_obj else "system@app",
            "actor_role": role_name,
            "vaction": log.vaction,
            "vtarget_model": log.vtarget_model,
            "vtarget_identifier": log.vtarget_identifier,
            "jbefore": log.jbefore,
            "jafter": log.jafter,
            "vip_address": log.vip_address,
            "dtimestamp": log.dtimestamp
        })

    return {"data": results, "total": total, "page": page, "limit": limit}

def get_security_logs(db: Session, page: int = 1, limit: int = 10, search: Optional[str] = None, event: Optional[str] = None, start_date: Optional[date] = None, end_date: Optional[date] = None, actor_id: Optional[int] = None):
    query = db.query(securityLogModel.SecurityLog).outerjoin(usersModel.User, securityLogModel.SecurityLog.nid_user == usersModel.User.nid)

    if search:
        search_fmt = f"%{search}%"
        query = query.filter(or_(usersModel.User.vname.ilike(search_fmt), usersModel.User.vemail.ilike(search_fmt), securityLogModel.SecurityLog.vip_address.ilike(search_fmt), securityLogModel.SecurityLog.vaction.ilike(search_fmt)))

    if event: query = query.filter(securityLogModel.SecurityLog.vaction.ilike(f"%{event}%"))
    if start_date: query = query.filter(func.date(securityLogModel.SecurityLog.dtimestamp) >= start_date)
    if end_date: query = query.filter(func.date(securityLogModel.SecurityLog.dtimestamp) <= end_date)
    if actor_id: query = query.filter(securityLogModel.SecurityLog.nid_user == actor_id)

    total = query.count()
    logs = query.order_by(desc(securityLogModel.SecurityLog.dtimestamp)).offset((page - 1) * limit).limit(limit).all()
    
    results = []
    for log in logs:
        results.append({
            "nid": log.nid,
            "actor_name": log.user.vname if log.user else "Guest/System",
            "actor_email": log.user.vemail if log.user else None,
            "vaction": log.vaction,
            "vip_address": log.vip_address,
            "vuser_agent": log.vuser_agent,
            "vdetails": log.vdetails,
            "dtimestamp": log.dtimestamp
        })

    return {"data": results, "total": total, "page": page, "limit": limit}

def _get_stats_by_date_range(db: Session, start_date: date, end_date: date):
    act_query = db.query(activityLogModel.ActivityLog).filter(func.date(activityLogModel.ActivityLog.dtimestamp) >= start_date, func.date(activityLogModel.ActivityLog.dtimestamp) <= end_date)
    sec_query = db.query(securityLogModel.SecurityLog).filter(func.date(securityLogModel.SecurityLog.dtimestamp) >= start_date, func.date(securityLogModel.SecurityLog.dtimestamp) <= end_date)
    # Hitung distinct IP untuk sinyal sumber akses unik
    distinct_ips = sec_query.with_entities(securityLogModel.SecurityLog.vip_address).distinct().count()
    # Unique actors lebih relevan dari security log (aktor keamanan), bukan activity log
    unique_security_actors = sec_query.with_entities(securityLogModel.SecurityLog.nid_user).distinct().count()
    return {
        "total_activities": act_query.count(),
        "creates": act_query.filter(activityLogModel.ActivityLog.vaction == 'CREATE').count(),
        "updates": act_query.filter(activityLogModel.ActivityLog.vaction == 'UPDATE').count(),
        "deletes": act_query.filter(activityLogModel.ActivityLog.vaction == 'DELETE').count(),
        "total_security_events": sec_query.count(),
        "login_success": sec_query.filter(securityLogModel.SecurityLog.vaction == 'LOGIN_SUCCESS').count(),
        "failed_logins": sec_query.filter(or_(securityLogModel.SecurityLog.vaction == 'LOGIN_FAILED', securityLogModel.SecurityLog.vaction.ilike('%FAIL%'))).count(),
        "unique_actors": unique_security_actors,
        "distinct_ips": distinct_ips,
        "period_start": start_date, "period_end": end_date
    }

def get_audit_stats_daily(db: Session):
    today = now_wib().date()
    return _get_stats_by_date_range(db, today, today)

def get_audit_stats_weekly(db: Session):
    today = now_wib().date()
    start_week = today - timedelta(days=6)
    return _get_stats_by_date_range(db, start_week, today)

def get_audit_stats_monthly(db: Session):
    today = now_wib().date()
    start_month = today - timedelta(days=29)
    return _get_stats_by_date_range(db, start_month, today)

def _get_distribution_by_date_range(db: Session, start_date: date, end_date: date):
    act_results = db.query(activityLogModel.ActivityLog.vaction, func.count(activityLogModel.ActivityLog.nid)).filter(func.date(activityLogModel.ActivityLog.dtimestamp) >= start_date, func.date(activityLogModel.ActivityLog.dtimestamp) <= end_date).group_by(activityLogModel.ActivityLog.vaction).all()
    sec_results = db.query(securityLogModel.SecurityLog.vaction, func.count(securityLogModel.SecurityLog.nid)).filter(func.date(securityLogModel.SecurityLog.dtimestamp) >= start_date, func.date(securityLogModel.SecurityLog.dtimestamp) <= end_date).group_by(securityLogModel.SecurityLog.vaction).all()
    return {"activity": [{"label": row[0], "value": row[1]} for row in act_results], "security": [{"label": row[0], "value": row[1]} for row in sec_results], "period_start": start_date, "period_end": end_date}

def get_audit_distribution_daily(db: Session):
    today = now_wib().date()
    return _get_distribution_by_date_range(db, today, today)

def get_audit_distribution_weekly(db: Session):
    today = now_wib().date()
    start_week = today - timedelta(days=6)
    return _get_distribution_by_date_range(db, start_week, today)

def get_audit_distribution_monthly(db: Session):
    today = now_wib().date()
    start_month = today - timedelta(days=29)
    return _get_distribution_by_date_range(db, start_month, today)
