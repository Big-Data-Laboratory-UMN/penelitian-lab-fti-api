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
        
        # [FIX] Blok 'SEED LABS' yang duplikat dihapus

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

        # === [FIXED] SEED DEPARTMENT-LAB RELATION ===
        if db.query(DepartmentLab).count() == 0:
            print("Tabel 'tblr_department_lab' kosong, memulai proses seeding...")
            
            # [FIX] Ambil NID dari DB, jangan hardcode
            labs_db = {l.vcode: l.nid for l in db.query(Lab).all()}
            deps_db = {d.vcode: d.nid for d in db.query(Department).all()}

            department_lab_to_seed = [
                {'vcode': 'BDA_SI', 'nid_lab': labs_db.get('BDA'), 'nid_department': deps_db.get('SI'), 'vcreated_by': 'system-migration'},
                {'vcode': 'IOT_TK', 'nid_lab': labs_db.get('IOT'), 'nid_department': deps_db.get('TK'), 'vcreated_by': 'system-migration'},
                {'vcode': 'DIGINT_TK', 'nid_lab': labs_db.get('DIGINT'), 'nid_department': deps_db.get('TK'), 'vcreated_by': 'system-migration'},
                {'vcode': 'CYBER_TI', 'nid_lab': labs_db.get('CYBER'), 'nid_department': deps_db.get('TI'), 'vcreated_by': 'system-migration'},
                {'vcode': 'AI_TI', 'nid_lab': labs_db.get('AI'), 'nid_department': deps_db.get('TI'), 'vcreated_by': 'system-migration'},
            ]
            
            # Filter out None values just in case
            valid_seeds = [d for d in department_lab_to_seed if d['nid_lab'] is not None and d['nid_department'] is not None]
            
            db.add_all([DepartmentLab(**dl) for dl in valid_seeds])
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

        # === [FIXED] SEED USER ACCESS (LOGIC BARU) ===
        if db.query(UserAccess).count() == 0:
            print("Tabel 'tblr_user_access' kosong, memulai seeding...")
            
            # 1. Ambil semua data master yg relevan
            users = {u.vcode: u for u in db.query(User).all()}
            roles = {r.vcode: r for r in db.query(Role).all()}
            departments = {d.vcode: d for d in db.query(Department).all()}
            labs = {l.vcode: l for l in db.query(Lab).all()}
            
            # 2. Ambil relasi Lab-Departemen dari DB
            # Hasil: {'SI': ['BDA'], 'TK': ['IOT', 'DIGINT'], 'TI': ['CYBER', 'AI']}
            labs_by_dept_code = {}
            labs_nid_to_code = {l.nid: l.vcode for l in db.query(Lab).all()}
            deps_nid_to_code = {d.nid: d.vcode for d in db.query(Department).all()}
            dept_lab_links = db.query(DepartmentLab).all()

            for link in dept_lab_links:
                dept_code = deps_nid_to_code.get(link.nid_department)
                lab_code = labs_nid_to_code.get(link.nid_lab)
                if dept_code and lab_code:
                    if dept_code not in labs_by_dept_code:
                        labs_by_dept_code[dept_code] = []
                    labs_by_dept_code[dept_code].append(lab_code)

            all_lab_codes = list(labs.keys())
            seeds = []

            # --- Logic 1: Superadmin (66852) ---
            # Role SA, Dept FTI, semua Lab
            user_sa = users.get("66852")
            role_sa = roles.get("SA")
            dept_fti = departments.get("FTI")
            if user_sa and role_sa and dept_fti:
                for lab_code in all_lab_codes:
                    lab_obj = labs.get(lab_code)
                    if lab_obj:
                        seeds.append(UserAccess(
                            vcode=str(uuid.uuid4()),
                            nid_user=user_sa.nid,
                            nid_role=role_sa.nid,
                            nid_department=dept_fti.nid, # Dept FTI
                            nid_lab=lab_obj.nid,           # Tiap Lab
                            nstatus=1, vcreated_by="system-migration", dcreated_at=datetime.utcnow()
                        ))
            
            # --- Logic 2: Admin (66853) ---
            # Role ADM, Dept SI, semua Lab di bawah SI
            user_adm = users.get("66853")
            role_adm = roles.get("ADM")
            dept_si = departments.get("SI")
            if user_adm and role_adm and dept_si:
                labs_for_si = labs_by_dept_code.get("SI", []) # Harusnya cuma ['BDA']
                for lab_code in labs_for_si:
                    lab_obj = labs.get(lab_code)
                    if lab_obj:
                        seeds.append(UserAccess(
                            vcode=str(uuid.uuid4()),
                            nid_user=user_adm.nid,
                            nid_role=role_adm.nid,
                            nid_department=dept_si.nid, # Dept SI
                            nid_lab=lab_obj.nid,         # Lab BDA
                            nstatus=1, vcreated_by="system-migration", dcreated_at=datetime.utcnow()
                        ))

            # --- Logic 3: PIC (66854) ---
            # Role PIC, Dept SI, Lab BDA
            user_pic = users.get("66854")
            role_pic = roles.get("PIC")
            dept_pic_home = departments.get("SI") 
            lab_pic = labs.get("BDA")
            if user_pic and role_pic and dept_pic_home and lab_pic:
                 seeds.append(UserAccess(
                    vcode=str(uuid.uuid4()),
                    nid_user=user_pic.nid,
                    nid_role=role_pic.nid,
                    nid_department=dept_pic_home.nid, 
                    nid_lab=lab_pic.nid,          
                    nstatus=1, vcreated_by="system-migration", dcreated_at=datetime.utcnow()
                ))

            # --- Logic 4: Visitor (66855) ---
            # Role VSTR, Dept NULL, Lab NULL
            user_vstr = users.get("66855")
            role_vstr = roles.get("VSTR")
            if user_vstr and role_vstr:
                 seeds.append(UserAccess(
                    vcode=str(uuid.uuid4()),
                    nid_user=user_vstr.nid,
                    nid_role=role_vstr.nid,
                    nid_department=None, # Non-management
                    nid_lab=None,        # Non-management
                    nstatus=1, vcreated_by="system-migration", dcreated_at=datetime.utcnow()
                ))

            db.add_all(seeds)
            db.commit()
            print(f"✅ Seeding 'tblr_user_access' berhasil dengan {len(seeds)} baris.")
        else:
            print("⏭️  Data sudah ada di tabel 'tblr_user_access'.")

    finally:
        db.close()


if __name__ == "__main__":
    print("Menjalankan full seeder...")
    seed_data()
    print("🎉 Semua data berhasil dised!")