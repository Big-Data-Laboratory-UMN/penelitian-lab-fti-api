import os
from fastapi import FastAPI # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from services.api import rolesAPI, usersAPI, labAPI, departmentAPI, userAccessAPI, departmentLabAPI, filesAPI, facilityAPI, labFacilityAPI, bookingAPI, auditLogAPI, chatbotAPI, buildingAPI, knowledgeBaseAPI, labArticleAPI, landingPageAPI
from services import models 
from contextlib import asynccontextmanager
from services.database import engine, Base, SessionLocal
from services.controller import usersController, bookingController, labArticleController
import asyncio
import pytz
from datetime import datetime

jakarta_tz = pytz.timezone("Asia/Jakarta")

Base.metadata.create_all(bind=engine)

BASE_URL_FRONTEND = os.getenv("BASE_URL_FE", "http://localhost:3000")
origins = [
    BASE_URL_FRONTEND,
]

# KEAMANAN (VULN-001): matikan dokumentasi API di production.
# Set ENVIRONMENT=production di file .env server.
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"


def check_overdue_bookings_job():
    """
    Fungsi wrapper yg dipanggil scheduler buat cek booking overdue.
    """
    jakarta_tz = pytz.timezone("Asia/Jakarta")
    print(f"\n[CRON JOB RUN] Running check_overdue_bookings_job at {datetime.now(jakarta_tz)}")
    db = SessionLocal()
    try:
        result = bookingController.trigger_update_overdue_bookings(db)
        print(f"[CRON JOB SUCCESS] Updated {result.get('updated_count', 0)} bookings.")
    except Exception as e:
        print(f"[CRON JOB FAILED] Error: {e}")
        db.rollback()
    finally:
        db.close()
    print("[CRON JOB FINISH] Job finished.")


def publish_scheduled_articles_job():
    """
    Cron job to publish scheduled articles.
    """
    jakarta_tz = pytz.timezone("Asia/Jakarta")
    print(f"\n[CRON JOB RUN] Running publish_scheduled_articles_job at {datetime.now(jakarta_tz)}")
    db = SessionLocal()
    try:
        result = labArticleController.publish_scheduled_articles(db)
        print(f"[CRON JOB SUCCESS] Published {result.get('updated_count', 0)} articles: {result.get('articles', [])}")
    except Exception as e:
        print(f"[CRON JOB FAILED] Error: {e}")
        db.rollback()
    finally:
        db.close()
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

        print("Menambahkan job 'publish_scheduled_articles_job'...")
        try:
            app.state.scheduler.add_job(
                publish_scheduled_articles_job,    
                'interval',                    
                minutes=1,                   
                id="job_publish_scheduled_articles",     
                replace_existing=True,        
                misfire_grace_time=60          
            )
            print("✅ Job 'publish_scheduled_articles_job' berhasil ditambahkan, akan jalan tiap 1 menit.")
        except Exception as e:
            print(f"❌ GAGAL menambahkan job 'publish_scheduled_articles_job': {e}")

        print("\n[STARTUP] Checking for scheduled articles...")
        startup_db = SessionLocal()
        try:
            now = datetime.now(jakarta_tz).replace(tzinfo=None)

            overdue_result = labArticleController.publish_scheduled_articles(startup_db)
            if overdue_result.get('updated_count', 0) > 0:
                print(f"[STARTUP] ✅ Published {overdue_result['updated_count']} overdue articles: {overdue_result['articles']}")
            else:
                print("[STARTUP] No overdue articles to publish.")

            from services.models import labArticleModel as articlesModel
            future_articles = startup_db.query(articlesModel.LabArticle).filter(
                articlesModel.LabArticle.nstatus == 2,
                articlesModel.LabArticle.dpublished_at != None,
                articlesModel.LabArticle.dpublished_at > now
            ).all()

            scheduled_count = 0
            for article in future_articles:
                success = labArticleController.schedule_article_publish(
                    scheduler=app.state.scheduler,
                    db_factory=SessionLocal,
                    article_vcode=article.vcode,
                    publish_datetime=article.dpublished_at
                )
                if success:
                    scheduled_count += 1

            if scheduled_count > 0:
                print(f"[STARTUP] ✅ Re-scheduled {scheduled_count} future articles.")
            else:
                print("[STARTUP] No future scheduled articles to re-schedule.")

        except Exception as e:
            print(f"[STARTUP] ❌ Error during startup article check: {e}")
        finally:
            startup_db.close()
        print("[STARTUP] Article scheduling check complete.\n")

        print("[STARTUP] Checking for approved bookings to expire...")
        booking_startup_db = SessionLocal()
        try:
            now = datetime.now(jakarta_tz).replace(tzinfo=None)

            overdue_result = bookingController.trigger_update_overdue_bookings(booking_startup_db)
            if overdue_result.get('updated_count', 0) > 0:
                print(f"[STARTUP] ✅ Expired {overdue_result['updated_count']} overdue bookings.")
            else:
                print("[STARTUP] No overdue bookings to expire.")

            from services.models.bookingModel import Booking as BookingModel
            future_bookings = booking_startup_db.query(BookingModel).filter(
                BookingModel.nstatus == 1,
                BookingModel.dend != None,
                BookingModel.dend > now
            ).all()

            scheduled_booking_count = 0
            for booking in future_bookings:
                success = bookingController.schedule_booking_expiration(
                    scheduler=app.state.scheduler,
                    db_factory=SessionLocal,
                    booking_id=booking.nid,
                    end_datetime=booking.dend
                )
                if success:
                    scheduled_booking_count += 1

            if scheduled_booking_count > 0:
                print(f"[STARTUP] ✅ Re-scheduled {scheduled_booking_count} future booking expirations.")
            else:
                print("[STARTUP] No future approved bookings to re-schedule.")

        except Exception as e:
            print(f"[STARTUP] ❌ Error during startup booking check: {e}")
        finally:
            booking_startup_db.close()
        print("[STARTUP] Booking expiration check complete.\n")
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
    lifespan=lifespan,
    # KEAMANAN (VULN-001): dokumentasi mati di production, nyala saat development
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

origins = [
    "http://labfti.umn.ac.id",
    "https://labfti.umn.ac.id",
]

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
app.include_router(usersAPI.router)
app.include_router(labAPI.router)
app.include_router(departmentAPI.router)
app.include_router(departmentLabAPI.router)
app.include_router(userAccessAPI.router)
app.include_router(filesAPI.router)
app.include_router(facilityAPI.router)
app.include_router(labFacilityAPI.router)
app.include_router(bookingAPI.router)
app.include_router(auditLogAPI.router)
app.include_router(chatbotAPI.router)
app.include_router(buildingAPI.router)
app.include_router(knowledgeBaseAPI.router)
app.include_router(labArticleAPI.router)
app.include_router(landingPageAPI.router)