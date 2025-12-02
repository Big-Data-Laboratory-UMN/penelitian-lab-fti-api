from fastapi import APIRouter, Depends, Query, HTTPException, Path
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from ..database import get_db
from ..controller import auditLogController, usersController
from ..schemas import auditLogSchema, usersSchema
from ..models import rolesModel, userAccessModel

router = APIRouter(
    prefix="/audit-logs",
    tags=["Audit Logs (Monitoring)"],
    responses={404: {"description": "Not found"}},
)

# ==========================================
# SECURITY & AUTHORIZATION
# ==========================================
def check_sa_access(db: Session, user: usersSchema.User):
    # (Logic otorisasi tetap sama)
    user_access = db.query(userAccessModel.UserAccess).join(rolesModel.Role)\
        .filter(
            userAccessModel.UserAccess.nid_user == user.nid,
            rolesModel.Role.vcode == 'SA', 
            userAccessModel.UserAccess.nstatus == 1
        ).first()
    
    if not user_access:
        raise HTTPException(status_code=403, detail="Access Denied: Dashboard Audit Log restricted to Superadmins only.")

def check_non_visitor_access(db: Session, user: usersSchema.User):
    # Cek apakah user punya role selain VISITOR yang aktif
    user_access = db.query(userAccessModel.UserAccess).join(rolesModel.Role)\
        .filter(
            userAccessModel.UserAccess.nid_user == user.nid,
            rolesModel.Role.vcode != 'VISITOR', 
            userAccessModel.UserAccess.nstatus == 1
        ).first()
    
    if not user_access:
        raise HTTPException(status_code=403, detail="Access Denied: Restricted to Non-Visitor users.")

# ==========================================
# ENDPOINTS
# ==========================================

# --- LIST ACTIVITY LOGS ---
@router.get("/activity", response_model=auditLogSchema.PaginatedActivityLog)
def read_activity_logs_api(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    startDate: Optional[date] = Query(None),
    endDate: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_sa_access(db, current_user)
    return auditLogController.get_activity_logs(db=db, page=page, limit=limit, search=search, module=module, action=action, start_date=startDate, end_date=endDate)

# --- DETAIL ACTIVITY LOG (NEW) ---
@router.get("/activity/{log_id}", response_model=auditLogSchema.ActivityLogResponse)
def read_activity_log_detail_api(
    log_id: int = Path(..., description="ID (nid) of the Activity Log"),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil detail lengkap satu Activity Log berdasarkan ID-nya.
    """
    check_sa_access(db, current_user)
    return auditLogController.get_activity_log_by_id(db=db, log_id=log_id)

# --- LIST BOOKING ACTIVITY LOGS (TIME RANGES) ---
@router.get("/activity/booking/24h", response_model=auditLogSchema.BookingActivityLogListResponse)
def read_booking_activity_logs_24h_api(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil activity log Booking 24 jam terakhir.
    """
    check_non_visitor_access(db, current_user)
    return auditLogController.get_booking_activity_logs_24h(db=db, current_user=current_user)

@router.get("/activity/booking/7days", response_model=auditLogSchema.BookingActivityLogListResponse)
def read_booking_activity_logs_7days_api(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil activity log Booking 7 hari terakhir.
    """
    check_non_visitor_access(db, current_user)
    return auditLogController.get_booking_activity_logs_7days(db=db, current_user=current_user)

@router.get("/activity/booking/30days", response_model=auditLogSchema.BookingActivityLogListResponse)
def read_booking_activity_logs_30days_api(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil activity log Booking 30 hari terakhir.
    """
    check_non_visitor_access(db, current_user)
    return auditLogController.get_booking_activity_logs_30days(db=db, current_user=current_user)

# --- LIST SECURITY LOGS ---
@router.get("/security", response_model=auditLogSchema.PaginatedSecurityLog)
def read_security_logs_api(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    event: Optional[str] = Query(None),
    startDate: Optional[date] = Query(None),
    endDate: Optional[date] = Query(None),
    actorId: Optional[int] = Query(None, alias="actorId"),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_sa_access(db, current_user)
    return auditLogController.get_security_logs(db=db, page=page, limit=limit, search=search, event=event, start_date=startDate, end_date=endDate, actor_id=actorId)

# --- DETAIL SECURITY LOG (NEW) ---
@router.get("/security/{log_id}", response_model=auditLogSchema.SecurityLogResponse)
def read_security_log_detail_api(
    log_id: int = Path(..., description="ID (nid) of the Security Log"),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil detail lengkap satu Security Log berdasarkan ID-nya.
    """
    check_sa_access(db, current_user)
    return auditLogController.get_security_log_by_id(db=db, log_id=log_id)


# --- STATS & DISTRIBUTION (TETAP SAMA) ---
@router.get("/stats", response_model=auditLogSchema.AuditStats)
def read_audit_stats_daily_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_stats_daily(db)

@router.get("/stats/weekly", response_model=auditLogSchema.AuditStats)
def read_audit_stats_weekly_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_stats_weekly(db)

@router.get("/stats/monthly", response_model=auditLogSchema.AuditStats)
def read_audit_stats_monthly_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_stats_monthly(db)

@router.get("/distribution", response_model=auditLogSchema.DistributionResponse)
def read_audit_distribution_daily_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_distribution_daily(db)

from fastapi import APIRouter, Depends, Query, HTTPException, Path
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from ..database import get_db
from ..controller import auditLogController, usersController
from ..schemas import auditLogSchema, usersSchema
from ..models import rolesModel, userAccessModel

router = APIRouter(
    prefix="/audit-logs",
    tags=["Audit Logs (Monitoring)"],
    responses={404: {"description": "Not found"}},
)

# ==========================================
# SECURITY & AUTHORIZATION
# ==========================================
def check_sa_access(db: Session, user: usersSchema.User):
    # (Logic otorisasi tetap sama)
    user_access = db.query(userAccessModel.UserAccess).join(rolesModel.Role)\
        .filter(
            userAccessModel.UserAccess.nid_user == user.nid,
            rolesModel.Role.vcode == 'SA', 
            userAccessModel.UserAccess.nstatus == 1
        ).first()
    
    if not user_access:
        raise HTTPException(status_code=403, detail="Access Denied: Dashboard Audit Log restricted to Superadmins only.")

def check_non_visitor_access(db: Session, user: usersSchema.User):
    # Cek apakah user punya role selain VISITOR yang aktif
    user_access = db.query(userAccessModel.UserAccess).join(rolesModel.Role)\
        .filter(
            userAccessModel.UserAccess.nid_user == user.nid,
            rolesModel.Role.vcode != 'VISITOR', 
            userAccessModel.UserAccess.nstatus == 1
        ).first()
    
    if not user_access:
        raise HTTPException(status_code=403, detail="Access Denied: Restricted to Non-Visitor users.")

# ==========================================
# ENDPOINTS
# ==========================================

# --- LIST ACTIVITY LOGS ---
@router.get("/activity", response_model=auditLogSchema.PaginatedActivityLog)
def read_activity_logs_api(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    startDate: Optional[date] = Query(None),
    endDate: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_sa_access(db, current_user)
    return auditLogController.get_activity_logs(db=db, page=page, limit=limit, search=search, module=module, action=action, start_date=startDate, end_date=endDate)

# --- DETAIL ACTIVITY LOG (NEW) ---
@router.get("/activity/{log_id}", response_model=auditLogSchema.ActivityLogResponse)
def read_activity_log_detail_api(
    log_id: int = Path(..., description="ID (nid) of the Activity Log"),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil detail lengkap satu Activity Log berdasarkan ID-nya.
    """
    check_sa_access(db, current_user)
    return auditLogController.get_activity_log_by_id(db=db, log_id=log_id)

# --- LIST BOOKING ACTIVITY LOGS (TIME RANGES) ---
@router.get("/activity/booking/24h", response_model=auditLogSchema.BookingActivityLogListResponse)
def read_booking_activity_logs_24h_api(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil activity log Booking 24 jam terakhir.
    """
    check_non_visitor_access(db, current_user)
    return auditLogController.get_booking_activity_logs_24h(db=db, current_user=current_user)

@router.get("/activity/booking/7days", response_model=auditLogSchema.BookingActivityLogListResponse)
def read_booking_activity_logs_7days_api(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil activity log Booking 7 hari terakhir.
    """
    check_non_visitor_access(db, current_user)
    return auditLogController.get_booking_activity_logs_7days(db=db, current_user=current_user)

@router.get("/activity/booking/30days", response_model=auditLogSchema.BookingActivityLogListResponse)
def read_booking_activity_logs_30days_api(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil activity log Booking 30 hari terakhir.
    """
    check_non_visitor_access(db, current_user)
    return auditLogController.get_booking_activity_logs_30days(db=db, current_user=current_user)

# --- LIST SECURITY LOGS ---
@router.get("/security", response_model=auditLogSchema.PaginatedSecurityLog)
def read_security_logs_api(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    event: Optional[str] = Query(None),
    startDate: Optional[date] = Query(None),
    endDate: Optional[date] = Query(None),
    actorId: Optional[int] = Query(None, alias="actorId"),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_sa_access(db, current_user)
    return auditLogController.get_security_logs(db=db, page=page, limit=limit, search=search, event=event, start_date=startDate, end_date=endDate, actor_id=actorId)

# --- DETAIL SECURITY LOG (NEW) ---
@router.get("/security/{log_id}", response_model=auditLogSchema.SecurityLogResponse)
def read_security_log_detail_api(
    log_id: int = Path(..., description="ID (nid) of the Security Log"),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil detail lengkap satu Security Log berdasarkan ID-nya.
    """
    check_sa_access(db, current_user)
    return auditLogController.get_security_log_by_id(db=db, log_id=log_id)


# --- STATS & DISTRIBUTION (TETAP SAMA) ---
@router.get("/stats", response_model=auditLogSchema.AuditStats)
def read_audit_stats_daily_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_stats_daily(db)

@router.get("/stats/weekly", response_model=auditLogSchema.AuditStats)
def read_audit_stats_weekly_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_stats_weekly(db)

@router.get("/stats/monthly", response_model=auditLogSchema.AuditStats)
def read_audit_stats_monthly_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_stats_monthly(db)

@router.get("/distribution", response_model=auditLogSchema.DistributionResponse)
def read_audit_distribution_daily_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_distribution_daily(db)

@router.get("/distribution/weekly", response_model=auditLogSchema.DistributionResponse)
def read_security_log_detail_api(
    log_id: int = Path(..., description="ID (nid) of the Security Log"),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil detail lengkap satu Security Log berdasarkan ID-nya.
    """
    check_sa_access(db, current_user)
    return auditLogController.get_security_log_by_id(db=db, log_id=log_id)


# --- STATS & DISTRIBUTION (TETAP SAMA) ---
@router.get("/stats", response_model=auditLogSchema.AuditStats)
def read_audit_stats_daily_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_stats_daily(db)

@router.get("/stats/weekly", response_model=auditLogSchema.AuditStats)
def read_audit_stats_weekly_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_stats_weekly(db)

@router.get("/stats/monthly", response_model=auditLogSchema.AuditStats)
def read_audit_stats_monthly_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_stats_monthly(db)

@router.get("/distribution", response_model=auditLogSchema.DistributionResponse)
def read_audit_distribution_daily_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_distribution_daily(db)

from fastapi import APIRouter, Depends, Query, HTTPException, Path
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from ..database import get_db
from ..controller import auditLogController, usersController
from ..schemas import auditLogSchema, usersSchema
from ..models import rolesModel, userAccessModel

router = APIRouter(
    prefix="/audit-logs",
    tags=["Audit Logs (Monitoring)"],
    responses={404: {"description": "Not found"}},
)

# ==========================================
# SECURITY & AUTHORIZATION
# ==========================================
def check_sa_access(db: Session, user: usersSchema.User):
    # (Logic otorisasi tetap sama)
    user_access = db.query(userAccessModel.UserAccess).join(rolesModel.Role)\
        .filter(
            userAccessModel.UserAccess.nid_user == user.nid,
            rolesModel.Role.vcode == 'SA', 
            userAccessModel.UserAccess.nstatus == 1
        ).first()
    
    if not user_access:
        raise HTTPException(status_code=403, detail="Access Denied: Dashboard Audit Log restricted to Superadmins only.")

def check_non_visitor_access(db: Session, user: usersSchema.User):
    # Cek apakah user punya role selain VISITOR yang aktif
    user_access = db.query(userAccessModel.UserAccess).join(rolesModel.Role)\
        .filter(
            userAccessModel.UserAccess.nid_user == user.nid,
            rolesModel.Role.vcode != 'VISITOR', 
            userAccessModel.UserAccess.nstatus == 1
        ).first()
    
    if not user_access:
        raise HTTPException(status_code=403, detail="Access Denied: Restricted to Non-Visitor users.")

# ==========================================
# ENDPOINTS
# ==========================================

# --- LIST ACTIVITY LOGS ---
@router.get("/activity", response_model=auditLogSchema.PaginatedActivityLog)
def read_activity_logs_api(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    startDate: Optional[date] = Query(None),
    endDate: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_sa_access(db, current_user)
    return auditLogController.get_activity_logs(db=db, page=page, limit=limit, search=search, module=module, action=action, start_date=startDate, end_date=endDate)

# --- DETAIL ACTIVITY LOG (NEW) ---
@router.get("/activity/{log_id}", response_model=auditLogSchema.ActivityLogResponse)
def read_activity_log_detail_api(
    log_id: int = Path(..., description="ID (nid) of the Activity Log"),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil detail lengkap satu Activity Log berdasarkan ID-nya.
    """
    check_sa_access(db, current_user)
    return auditLogController.get_activity_log_by_id(db=db, log_id=log_id)

# --- LIST BOOKING ACTIVITY LOGS (TIME RANGES) ---
@router.get("/activity/booking/24h", response_model=auditLogSchema.BookingActivityLogListResponse)
def read_booking_activity_logs_24h_api(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil activity log Booking 24 jam terakhir.
    """
    check_non_visitor_access(db, current_user)
    return auditLogController.get_booking_activity_logs_24h(db=db, current_user=current_user)

@router.get("/activity/booking/7days", response_model=auditLogSchema.BookingActivityLogListResponse)
def read_booking_activity_logs_7days_api(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil activity log Booking 7 hari terakhir.
    """
    check_non_visitor_access(db, current_user)
    return auditLogController.get_booking_activity_logs_7days(db=db, current_user=current_user)

@router.get("/activity/booking/30days", response_model=auditLogSchema.BookingActivityLogListResponse)
def read_booking_activity_logs_30days_api(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil activity log Booking 30 hari terakhir.
    """
    check_non_visitor_access(db, current_user)
    return auditLogController.get_booking_activity_logs_30days(db=db, current_user=current_user)

# --- LIST SECURITY LOGS ---
@router.get("/security", response_model=auditLogSchema.PaginatedSecurityLog)
def read_security_logs_api(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    event: Optional[str] = Query(None),
    startDate: Optional[date] = Query(None),
    endDate: Optional[date] = Query(None),
    actorId: Optional[int] = Query(None, alias="actorId"),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_sa_access(db, current_user)
    return auditLogController.get_security_logs(db=db, page=page, limit=limit, search=search, event=event, start_date=startDate, end_date=endDate, actor_id=actorId)

# --- DETAIL SECURITY LOG (NEW) ---
@router.get("/security/{log_id}", response_model=auditLogSchema.SecurityLogResponse)
def read_security_log_detail_api(
    log_id: int = Path(..., description="ID (nid) of the Security Log"),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil detail lengkap satu Security Log berdasarkan ID-nya.
    """
    check_sa_access(db, current_user)
    return auditLogController.get_security_log_by_id(db=db, log_id=log_id)


# --- STATS & DISTRIBUTION (TETAP SAMA) ---
@router.get("/stats", response_model=auditLogSchema.AuditStats)
def read_audit_stats_daily_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_stats_daily(db)

@router.get("/stats/weekly", response_model=auditLogSchema.AuditStats)
def read_audit_stats_weekly_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_stats_weekly(db)

@router.get("/stats/monthly", response_model=auditLogSchema.AuditStats)
def read_audit_stats_monthly_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_stats_monthly(db)

@router.get("/distribution", response_model=auditLogSchema.DistributionResponse)
def read_audit_distribution_daily_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_distribution_daily(db)

@router.get("/distribution/weekly", response_model=auditLogSchema.DistributionResponse)
def read_security_log_detail_api(
    log_id: int = Path(..., description="ID (nid) of the Security Log"),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil detail lengkap satu Security Log berdasarkan ID-nya.
    """
    check_sa_access(db, current_user)
    return auditLogController.get_security_log_by_id(db=db, log_id=log_id)


# --- STATS & DISTRIBUTION (TETAP SAMA) ---
@router.get("/stats", response_model=auditLogSchema.AuditStats)
def read_audit_stats_daily_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_stats_daily(db)

@router.get("/stats/weekly", response_model=auditLogSchema.AuditStats)
def read_audit_stats_weekly_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_stats_weekly(db)

@router.get("/stats/monthly", response_model=auditLogSchema.AuditStats)
def read_audit_stats_monthly_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_stats_monthly(db)

@router.get("/distribution", response_model=auditLogSchema.DistributionResponse)
def read_audit_distribution_daily_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_distribution_daily(db)

from fastapi import APIRouter, Depends, Query, HTTPException, Path
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from ..database import get_db
from ..controller import auditLogController, usersController
from ..schemas import auditLogSchema, usersSchema
from ..models import rolesModel, userAccessModel

router = APIRouter(
    prefix="/audit-logs",
    tags=["Audit Logs (Monitoring)"],
    responses={404: {"description": "Not found"}},
)

# ==========================================
# SECURITY & AUTHORIZATION
# ==========================================
def check_sa_access(db: Session, user: usersSchema.User):
    # (Logic otorisasi tetap sama)
    user_access = db.query(userAccessModel.UserAccess).join(rolesModel.Role)\
        .filter(
            userAccessModel.UserAccess.nid_user == user.nid,
            rolesModel.Role.vcode == 'SA', 
            userAccessModel.UserAccess.nstatus == 1
        ).first()
    
    if not user_access:
        raise HTTPException(status_code=403, detail="Access Denied: Dashboard Audit Log restricted to Superadmins only.")

def check_non_visitor_access(db: Session, user: usersSchema.User):
    # Cek apakah user punya role selain VISITOR yang aktif
    user_access = db.query(userAccessModel.UserAccess).join(rolesModel.Role)\
        .filter(
            userAccessModel.UserAccess.nid_user == user.nid,
            rolesModel.Role.vcode != 'VISITOR', 
            userAccessModel.UserAccess.nstatus == 1
        ).first()
    
    if not user_access:
        raise HTTPException(status_code=403, detail="Access Denied: Restricted to Non-Visitor users.")

# ==========================================
# ENDPOINTS
# ==========================================

# --- LIST ACTIVITY LOGS ---
@router.get("/activity", response_model=auditLogSchema.PaginatedActivityLog)
def read_activity_logs_api(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    startDate: Optional[date] = Query(None),
    endDate: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_sa_access(db, current_user)
    return auditLogController.get_activity_logs(db=db, page=page, limit=limit, search=search, module=module, action=action, start_date=startDate, end_date=endDate)

# --- DETAIL ACTIVITY LOG (NEW) ---
@router.get("/activity/{log_id}", response_model=auditLogSchema.ActivityLogResponse)
def read_activity_log_detail_api(
    log_id: int = Path(..., description="ID (nid) of the Activity Log"),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil detail lengkap satu Activity Log berdasarkan ID-nya.
    """
    check_sa_access(db, current_user)
    return auditLogController.get_activity_log_by_id(db=db, log_id=log_id)

# --- LIST BOOKING ACTIVITY LOGS (TIME RANGES) ---
@router.get("/activity/booking/24h", response_model=auditLogSchema.BookingActivityLogListResponse)
def read_booking_activity_logs_24h_api(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil activity log Booking 24 jam terakhir.
    """
    check_non_visitor_access(db, current_user)
    return auditLogController.get_booking_activity_logs_24h(db=db, current_user=current_user)

@router.get("/activity/booking/7days", response_model=auditLogSchema.BookingActivityLogListResponse)
def read_booking_activity_logs_7days_api(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil activity log Booking 7 hari terakhir.
    """
    check_non_visitor_access(db, current_user)
    return auditLogController.get_booking_activity_logs_7days(db=db, current_user=current_user)

@router.get("/activity/booking/30days", response_model=auditLogSchema.BookingActivityLogListResponse)
def read_booking_activity_logs_30days_api(
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil activity log Booking 30 hari terakhir.
    """
    check_non_visitor_access(db, current_user)
    return auditLogController.get_booking_activity_logs_30days(db=db, current_user=current_user)

# --- LIST SECURITY LOGS ---
@router.get("/security", response_model=auditLogSchema.PaginatedSecurityLog)
def read_security_logs_api(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    event: Optional[str] = Query(None),
    startDate: Optional[date] = Query(None),
    endDate: Optional[date] = Query(None),
    actorId: Optional[int] = Query(None, alias="actorId"),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_sa_access(db, current_user)
    return auditLogController.get_security_logs(db=db, page=page, limit=limit, search=search, event=event, start_date=startDate, end_date=endDate, actor_id=actorId)

# --- DETAIL SECURITY LOG (NEW) ---
@router.get("/security/{log_id}", response_model=auditLogSchema.SecurityLogResponse)
def read_security_log_detail_api(
    log_id: int = Path(..., description="ID (nid) of the Security Log"),
    db: Session = Depends(get_db),
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    """
    Ambil detail lengkap satu Security Log berdasarkan ID-nya.
    """
    check_sa_access(db, current_user)
    return auditLogController.get_security_log_by_id(db=db, log_id=log_id)


# --- STATS & DISTRIBUTION (TETAP SAMA) ---
@router.get("/stats", response_model=auditLogSchema.AuditStats)
def read_audit_stats_daily_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_stats_daily(db)

@router.get("/stats/weekly", response_model=auditLogSchema.AuditStats)
def read_audit_stats_weekly_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_stats_weekly(db)

@router.get("/stats/monthly", response_model=auditLogSchema.AuditStats)
def read_audit_stats_monthly_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_stats_monthly(db)

@router.get("/distribution", response_model=auditLogSchema.DistributionResponse)
def read_audit_distribution_daily_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_distribution_daily(db)

@router.get("/distribution/weekly", response_model=auditLogSchema.DistributionResponse)
def read_audit_distribution_weekly_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_distribution_weekly(db)

# --- SUPERADMIN STATS ---
@router.get("/superadmin-stats", response_model=auditLogSchema.SuperAdminStats)
def read_superadmin_stats_api(
    pulse_filter: Optional[str] = Query('24h', regex="^(24h|7d|30d|all_time)$"),
    threat_filter: Optional[str] = Query('24h', regex="^(24h|7d|30d|all_time)$"),
    infra_filter: Optional[str] = Query('all_labs'),
    peak_filter: Optional[str] = Query('all_labs'), # Added peak_filter
    db: Session = Depends(get_db), 
    current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)
):
    check_sa_access(db, current_user)
    return auditLogController.get_superadmin_stats(db, pulse_filter=pulse_filter, threat_filter=threat_filter, infra_filter=infra_filter, peak_filter=peak_filter)

@router.get("/distribution/monthly", response_model=auditLogSchema.DistributionResponse)
def read_audit_distribution_monthly_api(db: Session = Depends(get_db), current_user: usersSchema.User = Depends(usersController.get_current_active_user_from_cookie)):
    check_sa_access(db, current_user)
    return auditLogController.get_audit_distribution_monthly(db)