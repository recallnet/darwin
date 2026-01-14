"""
PostgreSQL database setup for Darwin API.

Configures SQLAlchemy engine, session, and declarative base for database operations.
"""

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://darwin:password@localhost:5432/darwin_web"
)

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Test connections before using them
    pool_size=10,  # Maximum number of connections
    max_overflow=20,  # Maximum overflow connections
    echo=False,  # Set to True for SQL query logging (dev only)
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI routes to get database session.

    Yields:
        Session: SQLAlchemy database session

    Example:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database by creating all tables.

    Note: In production, use Alembic migrations instead of this function.
    This is primarily for development and testing.
    """
    Base.metadata.create_all(bind=engine)
