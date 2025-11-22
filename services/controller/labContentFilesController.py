from sqlalchemy import or_, UniqueConstraint, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from ..models import labContentFilesModel as models
from ..schemas import labContentFilesSchema as schema

def get_lab_content_files(
        db: Session,
        vcode_lab_content: str,
):
    return db.query(models.LabContentFiles).filter(
        models.LabContentFiles.vcode_lab_content == vcode_lab_content
    ).all()