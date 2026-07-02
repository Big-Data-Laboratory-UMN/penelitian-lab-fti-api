# PANDUAN MENGGANTI EMAIL SMTP

**Lab Big Data FTI - Universitas Multimedia Nusantara**

## Pendahuluan

Dokumen ini adalah panduan lengkap untuk mengganti email SMTP yang digunakan di web FTI. Proses ini dibagi menjadi 2 bagian utama:

1. **Mengaktifkan Verifikasi 2 Langkah** dan mendapatkan Google App Password
2. **Mengganti App Password lama** dengan yang baru di server

Ikuti setiap langkah dengan teliti. Jika ada yang kurang jelas, tanyakan kepada koordinator lab FTI atau dosen pengurus lab Big Data.

---

## BAGIAN 1: Mengaktifkan Verifikasi 2 Langkah & Mendapat Google App Password

**Tujuan:** Mendapatkan App Password baru untuk SMTP dari akun email lab.

### Langkah 1: Login ke Akun Email Lab

1. Buka browser (Chrome, Firefox, Safari, Edge, dll) dan kunjungi:
   ```
   https://myaccount.google.com/
   ```

2. Masukkan email lab FTI:
   ```
   bigdata.lab@umn.ac.id
   ```

3. Klik tombol **'Berikutnya'**

4. Masukkan password akun email lab

   > ⚠️ **PERHATIAN:** Password bisa ditanyakan kepada:
   > - Koordinator Lab FTI
   > - Dosen Pengurus Lab Big Data

5. Klik tombol **'Berikutnya'** lagi untuk masuk ke akun

### Langkah 2: Buka Halaman Keamanan (Security)

1. Setelah berhasil login, di halaman Google Account, cari menu di sebelah kiri

2. Klik pada **'Keamanan'** (atau **'Security'**)

3. Pastikan sudah berada di halaman 'Keamanan' untuk melihat berbagai opsi keamanan akun

### Langkah 3: Aktifkan Verifikasi 2 Langkah (Jika Belum Aktif)

1. Di halaman Keamanan, cari bagian **'Verifikasi 2 Langkah'** atau **'2-Step Verification'**

2. Jika belum aktif, klik **'Aktifkan'** atau **'Enable'**

3. Google akan menampilkan pilihan verifikasi:
   - Pesan SMS
   - Panggilan telepon
   - Aplikasi Authenticator

4. Pilih salah satu sesuai kenyamanan Anda dan ikuti instruksi untuk menyelesaikan setup

### Langkah 4: Buat App Password Baru

1. Kembali ke halaman **Keamanan**, cari bagian **'App Passwords'** atau **'Password Aplikasi'**

2. Klik pada menu tersebut

3. Google akan menampilkan dropdown untuk memilih aplikasi dan perangkat:
   - Pilih **'Mail'** atau **'Email'** di menu pertama
   - Pilih **'Other (custom name)'** atau **'Windows/Linux/Mac'** di menu kedua, kemudian ketik **'FTI SMTP'**

4. Klik tombol **'Generate'** atau **'Buat'**

5. Google akan menampilkan password baru dengan format: `xxxx xxxx xxxx xxxx` (16 karakter dengan spasi)

### ⚠️ PENTING: Cara Menggunakan Google App Password

Google biasanya memberikan password dalam format: `xxxx xxxx xxxx xxxx`

**HAPUS SEMUA SPASI sebelum memasukkan ke web FTI!**

**Contoh:**
- Format dari Google: `a1b2 c3d4 e5f6 g7h8`
- Seharusnya dimasukkan ke web: `a1b2c3d4e5f6g7h8`

6. Salin password tersebut (Ctrl+C atau klik Copy)

7. Sekarang Anda siap untuk memasukkan password baru ke server web FTI (lihat Bagian 2)

---

## BAGIAN 2: Mengganti App Password di Server

**Tujuan:** Memperbarui file `.env` di server backend dengan Google App Password baru.

### Prasyarat

- Terhubung dengan WiFi khusus UMN atau VPN yang terhubung ke jaringan UMN
- Sudah memiliki aplikasi Terminal (Mac/Linux) atau PowerShell (Windows)
- Password akun SSH server (tanyakan ke Koordinator Lab FTI atau Dosen Pengurus Lab Big Data)

### Langkah 1: Buka Terminal atau PowerShell

**Untuk pengguna Windows:**
1. Tekan **Windows Key + R** untuk membuka Run dialog
2. Ketik `powershell` dan tekan Enter

**Untuk pengguna Mac/Linux:**
1. Buka Aplikasi **'Terminal'**

### Langkah 2: Hubungkan ke Server via SSH

1. Di Terminal atau PowerShell, ketik perintah berikut dan tekan Enter:
   ```bash
   ssh umnbigdata@10.200.1.25
   ```

2. Jika berhasil, sistem akan meminta password. Masukkan password akun SSH

   > ⚠️ **Password SSH:** Tanyakan ke Koordinator Lab FTI atau Dosen Pengurus Lab Big Data

3. Setelah berhasil login, terminal akan menampilkan prompt:
   ```
   umnbigdata@servername:~$
   ```

### Langkah 3: Navigasi ke Folder Backend

1. Ketik perintah berikut dan tekan Enter:
   ```bash
   cd ~/labfti/backend/penelitian-lab-fti-api
   ```

2. Sekarang Anda berada di folder backend yang berisi file konfigurasi `.env`

### Langkah 4: Edit File .env

Anda memiliki 2 pilihan editor: `nano` atau `vim`. Berikut penjelasan masing-masing:

#### PILIHAN 1: Menggunakan nano (Lebih Mudah untuk Pemula)

1. Ketik perintah berikut untuk membuka file `.env` dengan nano:
   ```bash
   nano .env
   ```

2. File `.env` akan terbuka. Anda akan melihat isi file dengan berbagai konfigurasi

3. Cari baris yang berisi `MAIL_PASSWORD`. Gunakan **Ctrl+W** untuk mencari:
   ```
   Tekan Ctrl+W → ketik 'MAIL_PASSWORD' → tekan Enter
   ```

4. Setelah menemukan baris `MAIL_PASSWORD`, posisikan kursor di akhir baris password lama

5. Gunakan tombol panah dan **Delete/Backspace** untuk menghapus password lama

6. Paste password baru yang sudah dicopy dari Google **(TANPA SPASI!)**

   **Contoh sebelum perubahan:**
   ```
   MAIL_PASSWORD=passwordlama123
   ```

   **Contoh setelah perubahan:**
   ```
   MAIL_PASSWORD=a1b2c3d4e5f6g7h8
   ```

7. Untuk menyimpan dan keluar dari nano:
   - Tekan **Ctrl+X**
   - Nano akan bertanya `Save modified buffer?`, ketik **Y** (Yes) dan tekan Enter
   - File akan disimpan dan Anda kembali ke terminal

#### PILIHAN 2: Menggunakan vim (Lebih Kuat tapi Lebih Sulit)

1. Ketik perintah berikut untuk membuka file `.env` dengan vim:
   ```bash
   vim .env
   ```

2. File `.env` akan terbuka. Vim memiliki dua mode: **Normal Mode** dan **Insert Mode**

3. Cari baris `MAIL_PASSWORD` dengan mengetik perintah pencarian:
   ```
   Tekan '/' → ketik 'MAIL_PASSWORD' → tekan Enter
   ```

4. Setelah menemukan baris, tekan **i** untuk masuk ke Insert Mode
   
   (Layar akan menampilkan `-- INSERT --` di bawah)

5. Gunakan tombol panah untuk navigasi. Hapus password lama dengan **Delete** atau **Backspace**

6. Paste password baru **(TANPA SPASI!)**

7. Tekan **Esc** untuk keluar dari Insert Mode

8. Ketik **:wq** (write + quit) dan tekan Enter untuk menyimpan dan keluar
   - `w` = write (simpan)
   - `q` = quit (keluar)

   > **Jika ingin keluar tanpa menyimpan, ketik `:q!` dan Enter**

### Langkah 5: Restart PM2

Setelah berhasil menyimpan file `.env`, aplikasi backend perlu di-restart agar perubahan password diterapkan.

1. Di terminal, ketik perintah berikut:
   ```bash
   pm2 restart all
   ```

   atau jika ingin restart aplikasi spesifik:
   ```bash
   pm2 restart [nama-aplikasi]
   ```

2. Tunggu hingga PM2 menyelesaikan restart (biasanya beberapa detik)

3. Untuk memastikan aplikasi sudah running dengan baik, ketik:
   ```bash
   pm2 status
   ```

Jika status menunjukkan **online**, berarti aplikasi sudah berjalan dengan baik dan email SMTP dengan password baru siap digunakan! ✅

---

## Troubleshooting (Jika Ada Masalah)

### Email masih tidak bisa dikirim setelah pergantian password

- Pastikan Anda sudah **menghapus spasi** dari Google App Password
- Pastikan **PM2 sudah di-restart** dengan benar
- Cek kembali bahwa Anda mengedit baris **MAIL_PASSWORD** yang benar
- Pastikan komputer terhubung dengan **WiFi UMN atau VPN** saat mengakses server

### Tidak bisa SSH ke server

- Pastikan komputer terhubung dengan **WiFi UMN atau VPN UMN**
- Pastikan **IP address server** (`10.200.1.25`) benar
- Pastikan **username** (`umnbigdata`) dan **password SSH** benar

### Lupa bagian mana yang harus diubah di file .env

- Hanya ubah **VALUE** (bagian setelah tanda `=`) dari baris `MAIL_PASSWORD`
- **Jangan ubah** nama parameter (bagian sebelum tanda `=`)
- **Jangan tambahkan atau hapus** baris baru

---

## Kontak Bantuan

Jika masih ada yang kurang jelas atau mengalami kendala, silakan hubungi:

- 📧 **Koordinator Lab FTI**
- 👨‍🏫 **Dosen Pengurus Lab Big Data**

---

**Dokumen ini dibuat untuk memastikan seluruh tim dapat mengelola konfigurasi SMTP dengan mudah dan konsisten.**

**Versi:** 1.0  
**Tanggal:** 2026
