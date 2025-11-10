from sqlalchemy import or_, UniqueConstraint, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from ..models import labContentFilesModel as models
from ..schemas import labContentFilesSchema as schema

def get_lab_content_file(
        db: Session,
        nid_lab_content: int,
):
    return db.query(models.LabContentFiles).filter(
        models.LabContentFiles.nid_lab_content == nid_lab_content
    ).all()