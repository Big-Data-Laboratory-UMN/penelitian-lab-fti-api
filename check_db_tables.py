from services.database import engine
from sqlalchemy import inspect

inspector = inspect(engine)
print("Tables in DB:")
for table_name in inspector.get_table_names():
    print(table_name)
