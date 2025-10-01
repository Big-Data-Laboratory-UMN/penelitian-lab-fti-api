from fastapi import FastAPI # type: ignore
from fastapi.middleware.cors import CORSMiddleware
from services.api import rolesAPI
import models
from database import engine

models.Base.metadata.create_all(bind=engine)

origins = [
    "http://localhost:3000",
]

app = FastAPI(
    title="FTI Lab Booking API",
    description="API untuk sistem peminjaman ruangan lab di FTI.",
    version="1.0.0"
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