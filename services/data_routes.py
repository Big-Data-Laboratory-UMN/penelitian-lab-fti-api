from fastapi import APIRouter

"""
Modul layanan (services) untuk aplikasi FastAPI.

File ini mendefinisikan sebuah router (`APIRouter`) yang berisi
endpoint terkait layanan data. Router ini nantinya akan di-include
ke dalam aplikasi utama (di file utama FastAPI, misalnya `main.py`).

Endpoint yang tersedia:
- GET /test -> Mengembalikan pesan sederhana sebagai health check
  untuk memastikan service data berjalan dengan benar.
"""

# Inisialisasi router untuk modularisasi endpoint
router = APIRouter()

@router.get("/test")
def test_data():
    return {"message": "Data Service OK"}
