from fastapi import FastAPI # type: ignore
from services.api import rolesAPI
import models
from database import engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FTI Lab Booking API",
    description="API untuk sistem peminjaman ruangan lab di FTI.",
    version="1.0.0"
)

@app.get("/", tags=["Root"])
def root():
    return {"message": "Welcome to FTI Lab Booking API!"}


app.include_router(rolesAPI.router)