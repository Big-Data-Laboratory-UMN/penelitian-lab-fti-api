# 📌 Penelitian FTI ML API

Proyek ini adalah contoh implementasi **FastAPI** dengan struktur modular untuk layanan API.  
Tujuan utama adalah menyediakan endpoint sederhana yang dapat dikembangkan menjadi layanan machine learning atau data processing.

---

## 🚀 Fitur
- Endpoint root (`/`) untuk memastikan server berjalan.
- Modul `services` dengan endpoint `/data/test` untuk pengecekan layanan data.
- Struktur project modular (dengan `APIRouter`) sehingga mudah dikembangkan.

## 🛠️ Cara Menjalankan

### 1. Clone Repository
```bash
git clone https://github.com/username/penelitian-lab-fti-ml-api.git
cd penelitian-lab-fti-ml-api
```

### 2. Buat Virtual Environment
```bash
python -m venv venv
```

### 3. Aktifkan Virtual Environment
```bash
venv\Scripts\activate -> windows
source venv/bin/activate -> linux/macOS
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Server
```bash
uvicorn main:app --reload
```

## 📚 Dokumentasi API

FastAPI otomatis menyediakan dokumentasi interaktif:

Swagger UI → http://127.0.0.1:8000/docs

ReDoc → http://127.0.0.1:8000/redoc

## 🧩 Komponen Penting

main.py → File utama, membuat instance FastAPI dan mendaftarkan router.

services/data_routes.py → Modul terpisah untuk routing service data.

requirements.txt → Berisi daftar package Python yang dibutuhkan.

venv/ → Virtual environment lokal (tidak perlu di-push ke GitHub).





