from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Render'da DATABASE_URL var, yerelde SQLite kullan
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./tarimAI.db")

# PostgreSQL URL'sini SQLAlchemy formatına çevir (Heroku/Render standart düzeltmesi)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Bulut veritabanı (Supabase/PostgreSQL) için bağlantı havuzu optimizasyonları
if DATABASE_URL.startswith("postgresql"):
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,          # Maksimum açık tutulacak bağlantı sayısı
        max_overflow=20,       # Havuz dolduğunda açılabilecek ekstra geçici bağlantı
        pool_recycle=1800,     # Yarım saatte bir bağlantıları yenile (Kopmaları önler)
        pool_pre_ping=True     # Her sorgudan önce bağlantı canlı mı diye kontrol et (Render dostu)
    )
else:
    # Yerel SQLite ayarı
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False} # FastAPI çoklu iş parçacığı güvenliği için
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()