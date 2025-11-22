from services.database import engine
from sqlalchemy import inspect

inspector = inspect(engine)
columns = inspector.get_columns('tblr_lab_gallery')
for column in columns:
    print(column['name'], column['type'])
