import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Use PostgreSQL on Railway (DATABASE_URL is set automatically)
# Falls back to SQLite for local development
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL:
    # Railway sets postgres:// but SQLAlchemy needs postgresql://
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
    print(f"[DB] Using PostgreSQL")
else:
    # Local development — use SQLite
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _DATA_DIR  = os.path.join(_BASE_DIR, "data")
    os.makedirs(_DATA_DIR, exist_ok=True)
    _SQLITE_URL = f"sqlite:///{os.path.join(_DATA_DIR, 'app.db')}"
    engine = create_engine(_SQLITE_URL, connect_args={"check_same_thread": False})
    print(f"[DB] Using SQLite (local dev)")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from db import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
