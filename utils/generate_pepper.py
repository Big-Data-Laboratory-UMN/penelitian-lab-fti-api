import os
import secrets
from pathlib import Path

# Nama file environment yang mau kita tuju
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
# Nama variabel untuk pepper
PEPPER_VARIABLE = "PASSWORD_PEPPER"

def generate_secure_pepper(length: int = 32) -> str:
    """Menghasilkan string acak yang aman secara kriptografis."""
    # secrets.token_hex(32) menghasilkan 64 karakter heksadesimal
    return secrets.token_hex(length)

def add_pepper_to_env():
    """
    Mengecek file .env, dan menambahkan pepper jika belum ada.
    """
    pepper_exists = False
    
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            for line in f:
                if line.strip().startswith(PEPPER_VARIABLE + "="):
                    pepper_exists = True
                    print(f"✅ Pepper '{PEPPER_VARIABLE}' sudah ada di file {ENV_FILE}.")
                    print("   Tidak ada perubahan yang dilakukan.")
                    break
    
    if not pepper_exists:
        print(f"⌛ Pepper '{PEPPER_VARIABLE}' tidak ditemukan. Membuat pepper baru...")
        
        new_pepper = generate_secure_pepper()
        
        # Tambahkan pepper ke file .env
        # Mode 'a' (append) akan membuat file jika belum ada, atau menambahkan ke baris terakhir jika sudah ada.
        with open(ENV_FILE, "a") as f:
            # Kita kasih newline di awal biar gak nyambung sama baris sebelumnya kalo filenya gak diakhiri enter
            f.write(f"\n{PEPPER_VARIABLE}='{new_pepper}'\n")
            
        print(f"🎉 Sukses! Pepper baru telah ditambahkan ke file {ENV_FILE}.")
        print(f"   Pepper Anda: {new_pepper}")

if __name__ == "__main__":
    add_pepper_to_env()