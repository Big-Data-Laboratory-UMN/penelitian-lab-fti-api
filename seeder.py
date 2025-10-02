from services.database import SessionLocal
from services.models import Role 

def seed_data():
    db = SessionLocal()

    try:
        if db.query(Role).count() == 0:
            print("Tabel 'tblm_roles' kosong, memulai proses seeding...")

            roles_to_seed = [
                {
                    'vcode': 'SA',
                    'vname': 'Super Administrator',
                    'vdesc': 'Has all permissions across the system.',
                    'vcreated_by': 'system-migration',
                },
                {
                    'vcode': 'ADM',
                    'vname': 'Administrator',
                    'vdesc': 'Manages users and system settings.',
                    'vcreated_by': 'system-migration',
                },
                {
                    'vcode': 'PIC',
                    'vname': 'PIC Lab',
                    'vdesc': 'Manages Labs Booking.',
                    'vcreated_by': 'system-migration',
                },
                {
                    'vcode': 'VSTR',
                    'vname': 'Visitor',
                    'vdesc': 'Standard user with basic permissions.',
                    'vcreated_by': 'system-migration',
                }
            ]

            for role_data in roles_to_seed:
                new_role = Role(**role_data)
                db.add(new_role)

            db.commit()
            print("Seeding berhasil! ✅")
        else:
            print("Data sudah ada di tabel 'tblm_roles', seeding dilewati. ⏭️")

    finally:
        db.close()

if __name__ == "__main__":
    print("Menjalankan seeder...")
    seed_data()
    print("Proses seeder selesai.")