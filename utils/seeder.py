import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent

sys.path.append(str(project_root))

from services.database import SessionLocal
from services.models import Role, Permissions, RolePermission

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
            print("Seeding berhasil 'tblm_roles'! ✅")
        else:
            print("Data sudah ada di tabel 'tblm_roles', seeding dilewati. ⏭️")
            
        if db.query(Permissions).count() == 0:
            print("Tabel 'tblm_permissions' kosong, memulai proses seeding...")

            permissions_to_seed = [
                # Global-level (Superadmin)
                {'vcode': 'LAB_VIEW_ALL', 'vname': 'View All Labs', 'vdesc': 'View all labs across all departments.', 'vcreated_by': 'system-migration'},
                {'vcode': 'LAB_MANAGE_ALL', 'vname': 'Manage All Labs', 'vdesc': 'Create, edit, and delete all labs.', 'vcreated_by': 'system-migration'},
                {'vcode': 'FACILITY_MANAGE_ALL', 'vname': 'Manage All Facilities', 'vdesc': 'Manage all lab facilities globally.', 'vcreated_by': 'system-migration'},
                {'vcode': 'SYS_CONFIG', 'vname': 'System Configuration', 'vdesc': 'Change system-wide settings.', 'vcreated_by': 'system-migration'},

                # Prodi-level (Admin)
                {'vcode': 'LAB_MANAGE_PRODI', 'vname': 'Manage Labs (Per Prodi)', 'vdesc': 'CRUD labs within assigned department.', 'vcreated_by': 'system-migration'},
                {'vcode': 'FACILITY_MANAGE_PRODI', 'vname': 'Manage Facilities (Per Prodi)', 'vdesc': 'CRUD facilities within assigned department.', 'vcreated_by': 'system-migration'},
                {'vcode': 'CONTENT_MANAGE_PRODI', 'vname': 'Manage Lab Content (Per Prodi)', 'vdesc': 'Manage lab content within assigned department.', 'vcreated_by': 'system-migration'},
                {'vcode': 'BOOKING_APPROVE_PRODI', 'vname': 'Approve Lab Bookings (Per Prodi)', 'vdesc': 'Approve or reject lab bookings in their department.', 'vcreated_by': 'system-migration'},

                # Lab-level (PIC)
                {'vcode': 'CONTENT_MANAGE_LAB', 'vname': 'Manage Lab Content (Per Lab)', 'vdesc': 'Manage lab content within assigned labs.', 'vcreated_by': 'system-migration'},
                {'vcode': 'BOOKING_APPROVE_LAB', 'vname': 'Approve Lab Bookings (Per Lab)', 'vdesc': 'Approve or reject lab bookings within assigned labs.', 'vcreated_by': 'system-migration'},
            ]

            for permission_data in permissions_to_seed:
                new_permission = Permissions(**permission_data)
                db.add(new_permission)

            db.commit()
            print("Seeding berhasil 'tblm_permissions'! ✅")
        else:
            print("Data sudah ada di tabel 'tblm_permissions', seeding dilewati. ⏭️")
        
        if db.query(RolePermission).count() == 0:
            print("Tabel 'tblr_role_permissions' kosong, memulai proses seeding...")

            roles = {r.vcode: r for r in db.query(Role).all()}
            permissions = {p.vcode: p for p in db.query(Permissions).all()}

            role_permissions_map = {
                # Super Admin dapat semuanya
                "SA": list(permissions.keys()),

                # Admin dapat level prodi
                "ADM": [
                    "LAB_MANAGE_PRODI",
                    "FACILITY_MANAGE_PRODI",
                    "CONTENT_MANAGE_PRODI",
                    "BOOKING_APPROVE_PRODI",
                ],

                # PIC Lab dapat level lab
                "PIC": [
                    "CONTENT_MANAGE_LAB",
                    "BOOKING_APPROVE_LAB",
                ],

                # Visitor cuma bisa lihat lab
                "VSTR": [
                    "LAB_VIEW_ALL",
                ],
            }

            seeding_data = []

            for role_code, perm_codes in role_permissions_map.items():
                role = roles.get(role_code)
                if not role:
                    print(f"⚠️ Role dengan kode {role_code} tidak ditemukan, dilewati.")
                    continue

                for perm_code in perm_codes:
                    permission = permissions.get(perm_code)
                    if not permission:
                        print(f"⚠️ Permission {perm_code} tidak ditemukan, dilewati.")
                        continue

                    data = RolePermission(
                        vcode=f"{role_code}_{perm_code}",
                        nid_role=role.nid,
                        nid_permission=permission.nid,
                        vcreated_by="system-migration",
                        nstatus=1
                    )
                    seeding_data.append(data)

            db.add_all(seeding_data)
            db.commit()
            print(f"Seeding berhasil 'tblr_role_permissions'! ✅")
        else:
            print("Data sudah ada di tabel 'tblr_role_permissions', seeding dilewati. ⏭️")

    finally:
        db.close()

if __name__ == "__main__":
    print("Menjalankan seeder...")
    seed_data()
    print("Proses seeder selesai.")