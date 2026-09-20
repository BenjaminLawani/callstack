import uuid
from sqlalchemy import (
    Column,
    DateTime,
    create_engine,
    func
)
from sqlalchemy.orm import (
    sessionmaker,
    declarative_base,
)
from .config import settings

class CreatedAtMixin:
    created_at = Column(DateTime(timezone=True),
                        default=func.now(), 
                        server_default=func.now())

class TimestampMixin:
    created_at = Column(DateTime(timezone=True),
                            default=func.now(), 
                            server_default=func.now())
    updated_at = Column(DateTime(timezone=True),
                            default=func.now(), 
                            server_default=func.now())

def generate_uuid() -> uuid.UUID:
    return uuid.uuid4()

Base = declarative_base()

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=60
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)