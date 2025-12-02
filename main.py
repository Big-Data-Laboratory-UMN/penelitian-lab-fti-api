import os
from fastapi import FastAPI # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from services.api import rolesAPI, permissionsAPI, rolesPermissionsAPI, usersAPI, labAPI, labContentAPI, labContentFilesAPI, landingPageAPI, landingPageImagesAPI, departmentAPI, userAccessAPI, departmentLabAPI, filesAPI, facilityAPI, labFacilityAPI, bookingAPI, auditLogAPI, labGalleryAPI, userPermissionsAPI
from services import models 
from contextlib import asynccontextmanager
from services.database import engine, Base, SessionLocal
from services.controller import usersController, bookingController
import asyncio
import pytz
from datetime import datetime

Base.metadata.create_all(bind=engine)

BASE_URL_FRONTEND = os.getenv("BASE_URL_FE", "http://localhost:3000")

origins = [
    BASE_URL_FRONTEND,
]

def check_overdue_bookings_job():
    """
    Fungsi wrapper yg dipanggil scheduler buat cek booking overdue.
    """
    # Set timezone
    jakarta_tz = pytz.timezone("Asia/Jakarta")
    print(f"\n[CRON JOB RUN] Running check_overdue_bookings_job at {datetime.now(jakarta_tz)}")
    db = SessionLocal() # Bikin DB session baru
    try:
        # Panggil fungsi controller yg asli
        result = bookingController.trigger_update_overdue_bookings(db)
        print(f"[CRON JOB SUCCESS] Updated {result.get('updated_count', 0)} bookings.")
    except Exception as e:
        print(f"[CRON JOB FAILED] Error: {e}")
        db.rollback() # Rollback kalo error
    finally:
        db.close() # Pastiin session ditutup
    print("[CRON JOB FINISH] Job finished.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    usersController.start_scheduler(app) 
    print("🔄 Lifespan started, scheduler initialized.")
    app.state.user_upload_locks = {}
    print("[*] Application startup: Initializing state...")
    app.state.lock_dict_lock = asyncio.Lock()
    print("[*] Application state (user_upload_locks, lock_dict_lock) initialized.")

    if hasattr(app.state, "scheduler") and app.state.scheduler.running:
        print("Menambahkan job 'check_overdue_bookings_job'...")
        try:
            app.state.scheduler.add_job(
                check_overdue_bookings_job,    
                'interval',                    
                hours=1,                       
                id="job_overdue_bookings",     
                replace_existing=True,        
                misfire_grace_time=60          
            )
            print("✅ Job 'check_overdue_bookings_job' berhasil ditambahkan, akan jalan tiap jam.")
        except Exception as e:
            print(f"❌ GAGAL menambahkan job 'check_overdue_bookings_job': {e}")
    else:
        print("⚠️ PERINGATAN: Scheduler tidak berjalan, job 'check_overdue_bookings' tidak bisa ditambahkan.")

    yield 

    print("[*] Application shutdown: Cleaning up...")
    if hasattr(app.state, "scheduler") and app.state.scheduler.running:
        app.state.scheduler.shutdown(wait=False)
        print("Scheduler dimatikan.")


app = FastAPI(
    title="FTI Lab Booking API",
    description="API untuk sistem peminjaman ruangan lab di FTI.",
    version="1.0.0",
    lifespan=lifespan 
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["Root"])
def root():
    return {"message": "Welcome to FTI Lab Booking API!"}


app.include_router(rolesAPI.router)
# app.include_router(permissionsAPI.router)
# app.include_router(rolesPermissionsAPI.router)
app.include_router(usersAPI.router)
app.include_router(userPermissionsAPI.router)
app.include_router(labAPI.router)
app.include_router(labGalleryAPI.router)
app.include_router(labContentAPI.router)
app.include_router(labContentFilesAPI.router)
app.include_router(landingPageAPI.router)
app.include_router(landingPageImagesAPI.router)
app.include_router(departmentAPI.router)
app.include_router(departmentLabAPI.router)
app.include_router(userAccessAPI.router)
app.include_router(filesAPI.router)
app.include_router(facilityAPI.router)
app.include_router(labFacilityAPI.router)
app.include_router(bookingAPI.router)
app.include_router(auditLogAPI.router)