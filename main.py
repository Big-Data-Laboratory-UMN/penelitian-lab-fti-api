from fastapi import FastAPI # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from services.api import rolesAPI, permissionsAPI, rolesPermissionsAPI, usersAPI, labAPI, departmentAPI, userAccessAPI, departmentLabAPI, filesAPI, facilityAPI, labFacilityAPI
from services import models 
from contextlib import asynccontextmanager
from services.database import engine, Base, SessionLocal
from services.controller import usersController
import asyncio

Base.metadata.create_all(bind=engine)

origins = [
    "http://localhost:3000",
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    usersController.start_scheduler(app)
    print("🔄 Lifespan started, scheduler initialized.")
    app.state.user_upload_locks = {}
    print("[*] Application startup: Initializing state...")
    app.state.lock_dict_lock = asyncio.Lock()
    print("[*] Application state (user_upload_locks, lock_dict_lock) initialized.")
    yield
    # Shutdown
    print("[*] Application shutdown: Cleaning up...")
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown(wait=False)


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
app.include_router(labAPI.router)
app.include_router(departmentAPI.router)
app.include_router(departmentLabAPI.router)
app.include_router(userAccessAPI.router)
app.include_router(filesAPI.router)
app.include_router(facilityAPI.router)
app.include_router(labFacilityAPI.router)