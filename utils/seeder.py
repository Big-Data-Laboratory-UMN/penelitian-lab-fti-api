import sys
from pathlib import Path
from datetime import datetime
import uuid

# === SETUP PATH PROJECT ROOT ===
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from services.database import SessionLocal
from services.models import (
    Role,
    Files,
    Facility,
    Lab,
    Department,
    DepartmentLab,
    LabFacility,
    User,
    UserAccess
)

def seed_data():
    db = SessionLocal()

    try:
        # === SEED LABS ===
        if db.query(Lab).count() == 0:
            print("Tabel 'tblm_lab' kosong, memulai proses seeding...")

            labs_to_seed = [
                {'vcode': 'BDA', 'vname': 'Lab Big Data', 'vdesc': 'Lab untuk penelitian Big Data.', 'ncapacity': 15,'vcreated_by': 'system-migration'},
                {'vcode': 'AI', 'vname': 'Lab Artificial Intelligence', 'vdesc': 'Lab penelitian AI.','ncapacity': 15, 'vcreated_by': 'system-migration'},
                {'vcode': 'DIGINT', 'vname': 'Lab Digital Interaction', 'vdesc': 'Lab Interaksi Digital.','ncapacity': 15, 'vcreated_by': 'system-migration'},
                {'vcode': 'CYBER', 'vname': 'Lab Cyber Security', 'vdesc': 'Lab Keamanan Siber.', 'ncapacity': 15, 'vcreated_by': 'system-migration'},
                {'vcode': 'IOT', 'vname': 'Lab Internet of Things', 'vdesc': 'Lab IoT.', 'ncapacity': 15, 'vcreated_by': 'system-migration'},
            ]
            db.add_all([Lab(**lab) for lab in labs_to_seed])
            db.commit()
            print("✅ Seeding berhasil 'tblm_lab'")
        else:
            print("⏭️  Data sudah ada di tabel 'tblm_lab'.")
        
        
        # === SEED LABS ===
        if db.query(Lab).count() == 0:
            print("Tabel 'tblm_lab' kosong, memulai proses seeding...")

            labs_to_seed = [
                {'vcode': 'BDA', 'vname': 'Lab Big Data', 'vdesc': 'Lab untuk penelitian Big Data.', 'ncapacity': 15,'vcreated_by': 'system-migration'},
                {'vcode': 'AI', 'vname': 'Lab Artificial Intelligence', 'vdesc': 'Lab penelitian AI.','ncapacity': 15, 'vcreated_by': 'system-migration'},
                {'vcode': 'DIGINT', 'vname': 'Lab Digital Interaction', 'vdesc': 'Lab Interaksi Digital.','ncapacity': 15, 'vcreated_by': 'system-migration'},
                {'vcode': 'CYBER', 'vname': 'Lab Cyber Security', 'vdesc': 'Lab Keamanan Siber.', 'ncapacity': 15, 'vcreated_by': 'system-migration'},
                {'vcode': 'IOT', 'vname': 'Lab Internet of Things', 'vdesc': 'Lab IoT.', 'ncapacity': 15, 'vcreated_by': 'system-migration'},
            ]
            db.add_all([Lab(**lab) for lab in labs_to_seed])
            db.commit()
            print("✅ Seeding berhasil 'tblm_lab'")
        else:
            print("⏭️  Data sudah ada di tabel 'tblm_lab'.")

        # === SEED DEPARTMENTS ===
        if db.query(Department).count() == 0:
            print("Tabel 'tblm_department' kosong, memulai proses seeding...")

            department_to_seed = [
                {'vcode': 'SI', 'vname': 'Prodi Sistem Informasi', 'vdesc': 'Departemen SI', 'vcreated_by': 'system-migration'},
                {'vcode': 'TK', 'vname': 'Prodi Teknik Komputer', 'vdesc': 'Departemen TK', 'vcreated_by': 'system-migration'},
                {'vcode': 'TI', 'vname': 'Prodi Teknik Informatika', 'vdesc': 'Departemen TI', 'vcreated_by': 'system-migration'},
                {'vcode': 'FTI', 'vname': 'Fakultas Teknik & Informatika', 'vdesc': 'Fakultas FTI', 'vcreated_by': 'system-migration'},
            ]
            db.add_all([Department(**dep) for dep in department_to_seed])
            db.commit()
            print("✅ Seeding berhasil 'tblm_department'")
        else:
            print("⏭️  Data sudah ada di tabel 'tblm_department'.")

        # === SEED DEPARTMENT-LAB RELATION ===
        if db.query(DepartmentLab).count() == 0:
            print("Tabel 'tblr_department_lab' kosong, memulai proses seeding...")
            department_lab_to_seed = [
                {'vcode': 'BDA_SI', 'nid_lab': 1, 'nid_department': 1, 'vcreated_by': 'system-migration'},
                {'vcode': 'IOT_TK', 'nid_lab': 5, 'nid_department': 2, 'vcreated_by': 'system-migration'},
                {'vcode': 'DIGINT_TK', 'nid_lab': 3, 'nid_department': 2, 'vcreated_by': 'system-migration'},
                {'vcode': 'CYBER_TI', 'nid_lab': 4, 'nid_department': 3, 'vcreated_by': 'system-migration'},
                {'vcode': 'AI_TI', 'nid_lab': 2, 'nid_department': 3, 'vcreated_by': 'system-migration'},
            ]
            db.add_all([DepartmentLab(**dl) for dl in department_lab_to_seed])
            db.commit()
            print("✅ Seeding berhasil 'tblr_department_lab'")
        else:
            print("⏭️  Data sudah ada di tabel 'tblr_department_lab'.")

        # === SEED ROLES ===
        if db.query(Role).count() == 0:
            print("Tabel 'tblm_roles' kosong, memulai proses seeding...")
            roles_to_seed = [
                {'vcode': 'SA', 'vname': 'Super Administrator', 'vdesc': 'Has all permissions.', 'vcreated_by': 'system-migration'},
                {'vcode': 'ADM', 'vname': 'Administrator', 'vdesc': 'Department-level management.', 'vcreated_by': 'system-migration'},
                {'vcode': 'PIC', 'vname': 'PIC Lab', 'vdesc': 'Lab-level management.', 'vcreated_by': 'system-migration'},
                {'vcode': 'VSTR', 'vname': 'Visitor', 'vdesc': 'View and book only.', 'vcreated_by': 'system-migration'},
            ]
            db.add_all([Role(**role) for role in roles_to_seed])
            db.commit()
            print("✅ Seeding berhasil 'tblm_roles'")
        else:
            print("⏭️  Data sudah ada di tabel 'tblm_roles'.")


        # === SEED USERS ===
        if db.query(User).count() == 0:
            print("Tabel 'tbls_users' kosong, memulai seeding user...")
            users_to_seed = [
                {'vcode': '66852', 'vname': 'Samuel Rai', 'vphone': '6285210647118', 'vemail': 'samuel.rai@student.umn.ac.id', 'vaddress': 'ABC', 'vpassword': '$argon2id$v=19$m=65536,t=3,p=4$iLF2rvUeQ0ipdS4F4BxjDA$hmbqKwgQKDh87EOQhpFW1sBHX4Ik8VKb0TsbgtSzEuw', 'nstatus': 1, 'vcreated_by': 'system-migration'},
                {'vcode': '66853', 'vname': 'Sammy Admin Prodi', 'vphone': '628111111111', 'vemail': 'samuelraylovers1@gmail.com', 'vaddress': 'Dept Office', 'vpassword': None, 'nstatus': 3, 'vcreated_by': 'system-migration'},
                {'vcode': '66854', 'vname': 'Ray PIC', 'vphone': '628222222222', 'vemail': 'samuelraylovers12@gmail.com', 'vaddress': 'Lab Office', 'vpassword': None, 'nstatus': 3, 'vcreated_by': 'system-migration'},
                {'vcode': '66855', 'vname': 'Visitor', 'vphone': '628333333333', 'vemail': 'samuelrayraz12@gmail.com', 'vaddress': 'Somewhere', 'vpassword': None, 'nstatus': 3, 'vcreated_by': 'system-migration'},
            ]
            db.add_all([User(**user) for user in users_to_seed])
            db.commit()
            print("✅ Seeding berhasil 'tbls_users'")
        else:
            print("⏭️  Data sudah ada di tabel 'tbls_users'.")

        # === SEED USER ACCESS ===
        if db.query(UserAccess).count() == 0:
            print("Tabel 'tblr_user_access' kosong, memulai seeding...")
            users = {u.vcode: u for u in db.query(User).all()}
            roles = {r.vcode: r for r in db.query(Role).all()}
            departments = {d.vcode: d for d in db.query(Department).all()}

            access_map = [
                ("66852", "SA", "FTI"),  # Superadmin di fakultas
                ("66853", "ADM", "SI"), # Admin SI
                ("66854", "PIC", "SI"), # PIC TK
                ("66855", "VSTR", "SI"), # Visitor TI
            ]

            seeds = []
            for user_code, role_code, dep_code in access_map:
                seeds.append(UserAccess(
                    vcode=str(uuid.uuid4()),
                    nid_user=users[user_code].nid,
                    nid_role=roles[role_code].nid,
                    nid_department=departments[dep_code].nid,
                    nstatus=1,
                    vcreated_by="system-migration",
                    dcreated_at=datetime.utcnow()
                ))

            db.add_all(seeds)
            db.commit()
            print("✅ Seeding berhasil 'tblr_user_access'")
        else:
            print("⏭️  Data sudah ada di tabel 'tblr_user_access'.")

    finally:
        db.close()


if __name__ == "__main__":
    print("Menjalankan full seeder...")
    seed_data()
    print("🎉 Semua data berhasil dised!")
