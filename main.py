from fastapi import FastAPI
from services import router as data_router

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello World"}

# Daftarkan router
app.include_router(data_router, prefix="/data", tags=["Data Services"])
