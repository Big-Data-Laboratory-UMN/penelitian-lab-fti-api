from fastapi import FastAPI
from services import router as data_router

"""
Aplikasi FastAPI sederhana dengan routing modular.

File ini mendefinisikan instance utama FastAPI (`app`) dan mengatur rute dasar
serta menggabungkan router tambahan dari modul `services`.

Struktur umum aplikasi:
- Endpoint root ("/") -> Mengembalikan pesan "Hello World".
- Router eksternal (`data_router`) -> Didaftarkan dengan prefix "/data" 
  dan dikelompokkan dalam tag "Data Services".
"""

app = FastAPI()

@app.get("/", summary="Root Endpoint", tags=["Root"])
def root():
    """
    Endpoint utama (root) aplikasi.

    Returns:
        dict: Pesan sederhana untuk memastikan aplikasi berjalan.
              Contoh output: {"message": "Hello World"}
    """
    return {"message": "Hello World"}


# Registrasi router eksternal dari modul `services`
# Router ini akan tersedia di bawah path "/data"
app.include_router(
    data_router,
    prefix="/data",          # Semua endpoint dalam router akan memiliki prefix ini
    tags=["Data Services"]   # Label/kelompok untuk dokumentasi OpenAPI
)
