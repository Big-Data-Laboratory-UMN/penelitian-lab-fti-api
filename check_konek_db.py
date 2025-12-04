from sqlalchemy import create_engine, text

DATABASE_URL = ""

try:
    # Bikin engine
    engine = create_engine(DATABASE_URL)
    
    # Coba connect
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 'SUCCESS: KONEKSI AMAN JAYA!'"))
        print("\n" + "="*40)
        print(result.scalar())
        print("="*40 + "\n")

except Exception as e:
    print("\n❌ GAGAL CONNECT BRO:")
    print(e)