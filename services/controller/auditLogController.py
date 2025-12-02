from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func, or_
from fastapi import Request, HTTPException, status
from datetime import datetime, date, timedelta
import pytz
from typing import Optional

# Import models
# Import models
from ..models import securityLogModel, activityLogModel, usersModel, bookingModel, labFacilityModel, labModel, departmentLabModel, userAccessModel, rolesModel, facilityModel

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

def _get_booking_logs_since(db: Session, start_time: datetime, current_user: usersModel.User, limit: int = 100):
    """
    Helper untuk ambil activity log Booking sejak waktu tertentu dengan SCOPING.
    """
    # 1. Base Query: Join ke Booking -> LabFacility -> Lab -> Facility
    query = db.query(activityLogModel.ActivityLog).join(
        bookingModel.Booking, activityLogModel.ActivityLog.vtarget_identifier == bookingModel.Booking.vcode
    ).join(
        labFacilityModel.LabFacility, bookingModel.Booking.nid_lab_facility == labFacilityModel.LabFacility.nid
    ).join(
        labModel.Lab, labFacilityModel.LabFacility.nid_lab == labModel.Lab.nid
    ).join(
        facilityModel.Facility, labFacilityModel.LabFacility.nid_facility == facilityModel.Facility.nid
    ).outerjoin(
        usersModel.User, activityLogModel.ActivityLog.nid_user == usersModel.User.nid
    )
    
    # 2. Filter Waktu & Module
    query = query.filter(
        activityLogModel.ActivityLog.vtarget_model == 'Booking',
        activityLogModel.ActivityLog.dtimestamp >= start_time
    )

    # 3. SCOPING LOGIC
    # Ambil semua role & akses user saat ini
    user_accesses = db.query(userAccessModel.UserAccess).join(rolesModel.Role).filter(
        userAccessModel.UserAccess.nid_user == current_user.nid,
        userAccessModel.UserAccess.nstatus == 1
    ).all()

    is_sa = False
    allowed_lab_ids = set()

    for access in user_accesses:
        role_code = access.role.vcode
        if role_code == 'SA':
            is_sa = True
            break # SA bisa lihat semua, gak perlu cek yg lain
        elif role_code == 'PIC':
            if access.nid_lab:
                allowed_lab_ids.add(access.nid_lab)
        elif role_code == 'ADM':
            if access.nid_department:
                # Ambil semua lab di department ini
                dept_labs = db.query(departmentLabModel.DepartmentLab.nid_lab).filter(
                    departmentLabModel.DepartmentLab.nid_department == access.nid_department,
                    departmentLabModel.DepartmentLab.nstatus == 1
                ).all()
                for (lab_id,) in dept_labs:
                    allowed_lab_ids.add(lab_id)

    if not is_sa:
        if not allowed_lab_ids:
            # User gak punya akses ke lab manapun (misal user biasa/visitor yg nyasar)
            return {"data": [], "total": 0}
        
        # Filter query berdasarkan allowed_lab_ids
        query = query.filter(labModel.Lab.nid.in_(allowed_lab_ids))
    
    # 4. Execute
    # Eager load booking -> lab_facility -> facility untuk akses vname
    logs = query.options(
        joinedload(activityLogModel.ActivityLog.user)
    ).order_by(desc(activityLogModel.ActivityLog.dtimestamp)).all()

    results = []
    for log in logs:
        user_obj = log.user
        role_name = "Unknown"
        if user_obj and hasattr(user_obj, 'user_access_rel') and user_obj.user_access_rel:
             active_access = next((ua for ua in user_obj.user_access_rel if ua.nstatus == 1), None)
             if active_access and active_access.role:
                 role_name = active_access.role.vname
        
        # Ambil facility name dari relasi Booking
        # Note: Kita query manual atau pake relasi yang ada.
        # Karena kita sudah join di query utama, kita bisa akses via relasi kalau sudah didefinisikan di model.
        # Tapi ActivityLog tidak punya relasi langsung ke Booking secara ORM (cuma vtarget_identifier).
        # Jadi kita harus ambil dari query result atau query ulang.
        # Cara paling efisien: Modifikasi query untuk select columns yang dibutuhkan atau eager load via join manual.
        # Tapi karena struktur ActivityLog generic, relasi ke Booking gak standard.
        # Workaround: Ambil Booking berdasarkan vcode (vtarget_identifier)
        
        # Optimization: Karena kita sudah join di query utama, kita bisa select entity Booking juga.
        # Tapi return type function ini diharapkan list of dict sesuai schema.
        
        # Let's use a simple lookup for now since we are iterating.
        # Or better, fetch the booking object inside the loop? No, N+1 problem.
        
        # Best approach given current architecture:
        # Since we filtered by join, the logs are correct.
        # To get facility name efficiently without changing ActivityLog model:
        # We can query (ActivityLog, Facility.vname) tuple.
        pass

    # RE-WRITE QUERY TO SELECT TUPLE (Log, FacilityName)
    # Ini lebih efisien daripada N+1
    
    results_tuple = db.query(activityLogModel.ActivityLog, facilityModel.Facility.vname).join(
        bookingModel.Booking, activityLogModel.ActivityLog.vtarget_identifier == bookingModel.Booking.vcode
    ).join(
        labFacilityModel.LabFacility, bookingModel.Booking.nid_lab_facility == labFacilityModel.LabFacility.nid
    ).join(
        labModel.Lab, labFacilityModel.LabFacility.nid_lab == labModel.Lab.nid
    ).join(
        facilityModel.Facility, labFacilityModel.LabFacility.nid_facility == facilityModel.Facility.nid
    ).outerjoin(
        usersModel.User, activityLogModel.ActivityLog.nid_user == usersModel.User.nid
    ).filter(
        activityLogModel.ActivityLog.vtarget_model == 'Booking',
        activityLogModel.ActivityLog.dtimestamp >= start_time
    )

    if not is_sa:
        if not allowed_lab_ids:
             return {"data": [], "total": 0}
        results_tuple = results_tuple.filter(labModel.Lab.nid.in_(allowed_lab_ids))

    logs_with_facility = results_tuple.order_by(desc(activityLogModel.ActivityLog.dtimestamp)).limit(limit).all()

    results = []
    for log, facility_name in logs_with_facility:
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
            "facility_name": facility_name, # Added field
            "vaction": log.vaction,
            "vtarget_model": log.vtarget_model,
            "vtarget_identifier": log.vtarget_identifier,
            "jbefore": log.jbefore,
            "jafter": log.jafter,
            "vip_address": log.vip_address,
            "dtimestamp": log.dtimestamp
        })


    return {"data": results, "total": len(results)}

def get_booking_activity_logs_24h(db: Session, current_user: usersModel.User, limit: int = 100):
    """Last 24 Hours"""
    start_time = now_wib() - timedelta(hours=24)
    return _get_booking_logs_since(db, start_time, current_user, limit)

def get_booking_activity_logs_7days(db: Session, current_user: usersModel.User, limit: int = 100):
    """Last 7 Days"""
    start_time = now_wib() - timedelta(days=7)
    return _get_booking_logs_since(db, start_time, current_user, limit)

def get_booking_activity_logs_30days(db: Session, current_user: usersModel.User, limit: int = 100):
    """Last 30 Days"""
    start_time = now_wib() - timedelta(days=30)
    return _get_booking_logs_since(db, start_time, current_user, limit)

def get_security_logs(db: Session, page: int = 1, limit: int = 10, search: Optional[str] = None, event: Optional[str] = None, start_date: Optional[date] = None, end_date: Optional[date] = None, actor_id: Optional[int] = None):
    query = db.query(securityLogModel.SecurityLog).outerjoin(usersModel.User, securityLogModel.SecurityLog.nid_user == usersModel.User.nid)

    if search:
        search_fmt = f"%{search}%"
        query = query.filter(or_(usersModel.User.vname.ilike(search_fmt), usersModel.User.vemail.ilike(search_fmt), securityLogModel.SecurityLog.vip_address.ilike(search_fmt), securityLogModel.SecurityLog.vaction.ilike(search_fmt)))

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

def get_superadmin_stats(db: Session, pulse_filter: str = '24h', threat_filter: str = '24h', infra_filter: str = 'all_labs', peak_filter: str = 'all_labs'):
    now = now_wib()
    
    # Helper to get start time based on filter
    def get_start_time(filter_type):
        if filter_type == '24h':
            return now - timedelta(hours=24)
        elif filter_type == '7d':
            return now - timedelta(days=7)
        elif filter_type == '30d':
            return now - timedelta(days=30)
        return None # all_time

    # 1. System Pulse (Health Score) - Uses pulse_filter
    pulse_start_time = get_start_time(pulse_filter)
    
    act_query = db.query(activityLogModel.ActivityLog)
    sec_query = db.query(securityLogModel.SecurityLog)
    
    if pulse_start_time:
        act_query = act_query.filter(activityLogModel.ActivityLog.dtimestamp >= pulse_start_time)
        sec_query = sec_query.filter(securityLogModel.SecurityLog.dtimestamp >= pulse_start_time)
        
    total_activities = act_query.count()
    total_security = sec_query.count()
    total_events = total_activities + total_security
    
    failed_events_query = db.query(securityLogModel.SecurityLog).filter(
        or_(securityLogModel.SecurityLog.vaction.ilike('%FAIL%'), securityLogModel.SecurityLog.vaction == 'LOGIN_FAILED')
    )
    if pulse_start_time:
        failed_events_query = failed_events_query.filter(securityLogModel.SecurityLog.dtimestamp >= pulse_start_time)
        
    failed_events = failed_events_query.count()
    
    system_pulse = 100.0
    if total_events > 0:
        system_pulse = ((total_events - failed_events) / total_events) * 100.0
        
    system_pulse_context = f"{failed_events} Error/Failures detected"

    # 2. Threat Level (Security Index) - Uses threat_filter
    threat_start_time = get_start_time(threat_filter)
    threat_prev_start_time = None
    
    if threat_filter == '24h':
        threat_prev_start_time = threat_start_time - timedelta(hours=24)
    elif threat_filter == '7d':
        threat_prev_start_time = threat_start_time - timedelta(days=7)
    elif threat_filter == '30d':
        threat_prev_start_time = threat_start_time - timedelta(days=30)
        
    threat_level = 0
    threat_query = db.query(securityLogModel.SecurityLog).filter(
        or_(securityLogModel.SecurityLog.vaction.ilike('%FAIL%'), securityLogModel.SecurityLog.vaction == 'LOGIN_FAILED')
    )
    
    if threat_start_time:
        threat_query = threat_query.filter(securityLogModel.SecurityLog.dtimestamp >= threat_start_time)
        
    threat_level = threat_query.count()
    
    threat_level_context = "All time record"
    if threat_prev_start_time and threat_start_time:
        failed_events_prev = db.query(securityLogModel.SecurityLog).filter(
            securityLogModel.SecurityLog.dtimestamp >= threat_prev_start_time,
            securityLogModel.SecurityLog.dtimestamp < threat_start_time,
            or_(securityLogModel.SecurityLog.vaction.ilike('%FAIL%'), securityLogModel.SecurityLog.vaction == 'LOGIN_FAILED')
        ).count()
        
        diff_threat = threat_level - failed_events_prev
        sign_threat = "+" if diff_threat >= 0 else ""
        threat_level_context = f"{sign_threat}{diff_threat} vs Previous Period"

    # 3. Infrastructure Load (Maintenance Ratio) - YEARLY COMPARISON
    # Logic: Total Maintenance Bookings (Current Year) vs Previous Year
    # Filter: infra_filter (all_labs or lab_id)
    
    current_year = now.year
    start_of_year = datetime(current_year, 1, 1, tzinfo=pytz.timezone("Asia/Jakarta"))
    start_of_prev_year = datetime(current_year - 1, 1, 1, tzinfo=pytz.timezone("Asia/Jakarta"))
    
    # Base Query Helper
    def get_infra_query(start_date, end_date=None):
        query = db.query(bookingModel.Booking).filter(
            bookingModel.Booking.nbooking_type == 1, # Maintenance
            bookingModel.Booking.dstart >= start_date
        )
        if end_date:
            query = query.filter(bookingModel.Booking.dstart < end_date)
            
        # Apply Lab Filter
        if infra_filter and infra_filter != 'all_labs':
            try:
                lab_id = int(infra_filter)
                query = query.join(
                    labFacilityModel.LabFacility, bookingModel.Booking.nid_lab_facility == labFacilityModel.LabFacility.nid
                ).join(
                    labModel.Lab, labFacilityModel.LabFacility.nid_lab == labModel.Lab.nid
                ).filter(labModel.Lab.nid == lab_id)
            except ValueError:
                pass # Ignore invalid filter
                
        return query

    # Current Year
    infrastructure_load = get_infra_query(start_of_year).count()
    
    # Previous Year
    infrastructure_load_prev = get_infra_query(start_of_prev_year, start_of_year).count()
    
    # Calculate % Change
    infra_diff_percent = 0.0
    if infrastructure_load_prev > 0:
        infra_diff_percent = ((infrastructure_load - infrastructure_load_prev) / infrastructure_load_prev) * 100.0
    elif infrastructure_load > 0:
        infra_diff_percent = 100.0 # From 0 to something is 100% increase (effectively infinite but capped for UI)
        
    sign_infra = "+" if infra_diff_percent >= 0 else ""
    infrastructure_load_context = f"{sign_infra}{round(infra_diff_percent, 1)}% vs Last Year"

    # 4. Peak Hour Velocity (Booking Rate) - LAST 30 DAYS
    # Logic: Total Approved Bookings (Last 30 Days) vs Previous 30 Days
    # Filter: peak_filter (all_labs or lab_id)
    # Context: "X Labs Full Booked" or "% Change"
    
    peak_delta = timedelta(days=30)
    peak_start = now - peak_delta
    peak_prev_start = peak_start - peak_delta
    
    def get_peak_query(start_date, end_date=None):
        query = db.query(bookingModel.Booking).filter(
            bookingModel.Booking.nstatus == 1, # Approved
            bookingModel.Booking.dstart >= start_date
        )
        if end_date:
            query = query.filter(bookingModel.Booking.dstart < end_date)
            
        # Apply Lab Filter
        if peak_filter and peak_filter != 'all_labs':
            try:
                lab_id = int(peak_filter)
                query = query.join(
                    labFacilityModel.LabFacility, bookingModel.Booking.nid_lab_facility == labFacilityModel.LabFacility.nid
                ).join(
                    labModel.Lab, labFacilityModel.LabFacility.nid_lab == labModel.Lab.nid
                ).filter(labModel.Lab.nid == lab_id)
            except ValueError:
                pass
        return query

    peak_hour_velocity = get_peak_query(peak_start).count()
    peak_prev_count = get_peak_query(peak_prev_start, peak_start).count()
    
    peak_change = 0.0
    if peak_prev_count > 0:
        peak_change = ((peak_hour_velocity - peak_prev_count) / peak_prev_count) * 100.0
    elif peak_hour_velocity > 0:
        peak_change = 100.0
    
    sign_peak = "+" if peak_change >= 0 else ""
    peak_change_str = f"{sign_peak}{round(peak_change, 1)}% vs Last 30 Days"
    
    # Full Booked Logic
    # Heuristic: Capacity * 20 working days
    full_booked_context = None
    
    if peak_filter == 'all_labs':
        # Check all labs
        labs = db.query(labModel.Lab).filter(labModel.Lab.nstatus == 1).all()
        full_booked_labs_count = 0
        
        for lab in labs:
            # Calculate capacity threshold
            capacity_threshold = lab.ncapacity * 20
            
            # Count bookings for this lab in last 30 days
            lab_bookings = db.query(bookingModel.Booking).join(
                labFacilityModel.LabFacility, bookingModel.Booking.nid_lab_facility == labFacilityModel.LabFacility.nid
            ).filter(
                bookingModel.Booking.nstatus == 1,
                bookingModel.Booking.dstart >= peak_start,
                labFacilityModel.LabFacility.nid_lab == lab.nid
            ).count()
            
            if lab_bookings >= capacity_threshold:
                full_booked_labs_count += 1
        
        if full_booked_labs_count > 0:
            full_booked_context = f"{full_booked_labs_count} Labs Full Booked"
            
    elif peak_filter != 'all_labs':
        try:
            lab_id = int(peak_filter)
            lab = db.query(labModel.Lab).filter(labModel.Lab.nid == lab_id).first()
            if lab:
                capacity_threshold = lab.ncapacity * 20
                if peak_hour_velocity >= capacity_threshold:
                    full_booked_context = "Full Booked"
        except ValueError:
            pass

    peak_hour_velocity_context = full_booked_context if full_booked_context else peak_change_str

    return {
        "system_pulse": round(system_pulse, 1),
        "system_pulse_context": system_pulse_context,
        "threat_level": threat_level,
        "threat_level_context": threat_level_context,
        "infrastructure_load": round(infrastructure_load, 1),
        "infrastructure_load_context": infrastructure_load_context,
        "peak_hour_velocity": peak_hour_velocity,
        "peak_hour_velocity_context": peak_hour_velocity_context
    }

