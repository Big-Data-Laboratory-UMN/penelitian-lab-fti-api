from fastapi import FastAPI # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from services.api import rolesAPI, permissionsAPI, rolesPermissionsAPI, usersAPI, labAPI, departmentAPI, userAccess, departmentLabAPI
from services import models 
from contextlib import asynccontextmanager
from services.database import engine, Base, SessionLocal
from services.controller import usersController

Base.metadata.create_all(bind=engine)

origins = [
    "http://localhost:3000",
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    usersController.start_scheduler(app)
    print("🔄 Lifespan started, scheduler initialized.")
    yield
    # Shutdown
    print("🛑 Lifespan shutting down, cleaning up scheduler.")
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
app.include_router(permissionsAPI.router)
app.include_router(rolesPermissionsAPI.router)
app.include_router(usersAPI.router)
app.include_router(labAPI.router)
app.include_router(departmentAPI.router)
app.include_router(departmentLabAPI.router)
app.include_router(userAccess.router)
