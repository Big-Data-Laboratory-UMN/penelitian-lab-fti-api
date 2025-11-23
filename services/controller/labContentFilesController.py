from sqlalchemy import or_, UniqueConstraint, and_, update
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from ..models import labContentFilesModel as models
from ..schemas import labContentFilesSchema as schema
from ..schemas import usersSchema

import pytz

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

def now_wib() -> datetime:
    return datetime.now(JAKARTA_TZ)

def get_lab_content_files(
        db: Session,
        vcode_lab_content: str,
):
    return db.query(models.LabContentFiles).filter(
        models.LabContentFiles.vcode_lab_content == vcode_lab_content,
        models.LabContentFiles.nstatus == 1
    ).all()

def create_lab_content_file(db: Session, file_data: schema.LabContentFileCreate, current_user: usersSchema.User):
    try:
        db_file = models.LabContentFiles(**file_data.model_dump())
        db_file.vcreated_by = current_user.vcode
        db_file.dcreated_at = now_wib()
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        return db_file
    except Exception as e:
        db.rollback()
        raise ValueError(f"Gagal menambahkan file content. {e}")

def delete_lab_content_file(db: Session, nid: int, current_user: usersSchema.User):
    try:
        stmt = update(models.LabContentFiles).where(
            models.LabContentFiles.nid == nid
        ).values(
            nstatus=0,
            vmodified_by=current_user.vcode,
            dmodified_at=now_wib()
        )
        db.execute(stmt)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise ValueError(f"Gagal menghapus file content. {e}")