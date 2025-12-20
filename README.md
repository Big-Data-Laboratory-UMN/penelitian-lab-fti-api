# 🧪 Penelitian Lab FTI - API Backend

Backend service yang tangguh dan modular untuk sistem peminjaman serta manajemen laboratorium FTI (Fakultas Teknologi Informasi). Dibangun di atas **FastAPI**, API ini menangani seluruh logika bisnis mulai dari autentikasi pengguna, validasi booking yang kompleks, hingga penjadwalan otomatis.

---

## 🌟 Fitur Unggulan

- **Autentikasi Modern & Aman**: Implementasi **Double Token** (Access & Refresh) yang disimpan dalam **HTTP-Only Cookies**, dimitigasi dari serangan XSS. Password diamankan dengan Argon2/Bcrypt + Pepper.
- **Role-Based Access Control (RBAC)**: Sistem hak akses granular. User bisa memiliki peran yang berbeda ('Admin', 'PIC', 'User') tergantung pada **Scope**-nya (Departemen atau Lab tertentu).
- **Sistem Booking Cerdas**:
  - Deteksi bentrok jadwal (collision detection) secara real-time.
  - Validasi aturan bisnis: Batas waktu booking harian (17:00 WIB) dan penutupan hari Minggu.
- **Background Tasks & Scheduler**: Menggunakan `APScheduler` untuk tugas otomatis seperti pembatalan booking yang expired atau publikasi artikel terjadwal.
- **Arsitektur Modular**: Pemisahan yang jelas antara Controller (Logic), Model (Data), dan API (Router) memudahkan maintenance dan scalability.

---


## 🛠️ Panduan Instalasi & Konfigurasi

### 1. Persyaratan Sistem
- **Python 3.10+**
- **MySQL 8.0+**
- **Git**

### 2. Setup Project

```bash
# Clone repository
git clone https://github.com/Big-Data-Laboratory-UMN/penelitian-lab-fti-ml-api.git
cd penelitian-lab-fti-ml-api

# Setup Virtual Environment
python -m venv venv

# Aktivasi Venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install Dependencies
pip install -r requirements.txt
```

### 3. Konfigurasi Environment Variable (`.env`)

Buat file `.env` di root folder dan lengkapi konfigurasi berikut. **PENTING:** Jangan kosongkan variabel keamanan.

#### Database & Server
| Variable | Deskripsi | Contoh |
| :--- | :--- | :--- |
| `DATABASE_URL` | Koneksi string ke MySQL | `mysql+pymysql://user:pass@localhost:3306/db_name` |
| `BASE_URL_FE` | URL Frontend (untuk CORS) | `http://localhost:3000` |
| `BASE_URL_BE` | URL Backend sendiri | `http://localhost:8000` |

#### Keamanan (Auth)
| Variable | Deskripsi | Default / Contoh |
| :--- | :--- | :--- |
| `SECRET_KEY` | Kunci enkripsi JWT (Wajib acak & panjang) | `super_secret_random_string` |
| `PASSWORD_PEPPER` | Tambahan string rahasia untuk hash password | `secret_pepper_string` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Durasi Access Token | `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Durasi Refresh Token | `30` |
| `COOKIE_SECURE` | HTTPS Only Cookies (True di Prod) | `True` / `False` |
| `COOKIE_SAMESITE` | Kebijakan SameSite Cookie | `lax` atau `strict` |

#### Layanan Email (SMTP)
Digunakan untuk aktivasi akun dan reset password.
| Variable | Deskripsi |
| :--- | :--- |
| `MAIL_USERNAME` | Email pengirim |
| `MAIL_PASSWORD` | Password aplikasi / SMTP |
| `MAIL_SERVER` | Host SMTP (misal: smtp.gmail.com) |
| `MAIL_PORT` | Port SMTP (587 untuk TLS) |

#### Penyimpanan File
| Variable | Deskripsi |
| :--- | :--- |
| `STORAGE_DIR` | Path absolut folder upload | `/path/to/project/storage` |

### 4. Setup Database & Migration (Alembic)

Karena Alembic hanya mengelola tabel (bukan membuat database itu sendiri), ikuti langkah berikut secara berurutan:

#### a. Buat Database Manual
Buka MySQL Client (Workbench/DBeaver/CLI) dan buat database kosong sesuai nama di `.env`.
```sql
CREATE DATABASE laboratorium_fti;
```

#### b. Generate Initial Migration
Jika folder `alembic/versions` masih kosong, jalankan perintah ini untuk membuat file migrasi pertama berdasarkan model yang ada.
```bash
# Pastikan sudah berada di root folder dan venv aktif
alembic revision --autogenerate -m "Initial migration"
```
*Perintah ini akan men-scan file di `services/models` dan membuat script python di `alembic/versions/`.*

#### c. Terapkan Migrasi (Init Tables)
Eksekusi file migrasi tersebut untuk membuat tabel fisik di database.
```bash
alembic upgrade head
```

#### d. Seeding Data Awal (Opsional)
Isi database dengan data master default (Role, User Admin, dll).
```bash
python -m utils.seeder
```

#### e. Alternatif (Jika Terkendala Alembic)
> **⚠️ Note:** Sangat disarankan untuk tetap menggunakan **Alembic Migration** (langkah b & c) agar struktur database selalu sinkron dengan kode Python dan menjaga keakuratan data.

Namun, jika Anda mengalami kesulitan teknis, Anda dapat meng-import file SQL yang telah disediakan secara manual:
1.  Pastikan database kosong sudah dibuat.
2.  Import file `sql/database.sql` ke database tersebut menggunakan MySQL Client pilihan Anda.

### 5. Menjalankan Server

#### Development Mode
Auto-reload aktif jika ada perubahan kode.
```bash
uvicorn main:app --reload
```

#### Production Mode
Menggunakan Gunicorn sebagai process manager.
```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## 📚 Struktur API Endpoint

API dibagi menjadi beberapa modul router utama yang terdaftar di `main.py`:

| Router Tag | Fungsi Utama |
| :--- | :--- |
| **Users** | Registrasi, Login (`/token`), Profile, Aktivasi Akun. |
| **Roles** | Manajemen Master Data Role (Admin only). |
| **Booking** | Create Booking, Approval Flow, Upload Dokumentasi. |
| **Lab** | CRUD Data Laboratorium. |
| **Facility** | Manajemen fasilitas/alat di dalam lab. |
| **AuditLog** | Mencatat aktivitas user dan keamanan (Login, Logout, Create). |
| **LandingPage** | Data publik untuk halaman depan (statistik, berita). |
| **Chatbot** | Layanan tanya jawab otomatis seputar lab. |

*Dokumentasi lengkap setiap endpoint tersedia di Swagger UI (`/docs`).*

---

## 🤝 Kontribusi & Pengembangan

1.  **Branching**: Gunakan branch `feature/nama-fitur` atau `fix/nama-bug`.
2.  **Controller Pattern**: Letakkan logika bisnis (validasi, query kompleks) di folder `services/controller/`, bukan di file API router.
3.  **Migrations**: Setiap perubahan model database **wajib** disertai dengan file revisi Alembic (`alembic revision --autogenerate`).
