from services.database import Base
from services import models

print("Tables in Base.metadata:")
for table in Base.metadata.tables:
    print(table)
