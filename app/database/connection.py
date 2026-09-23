from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config import POSTGRES_URL

engine: Engine = create_engine(
    POSTGRES_URL,
    pool_pre_ping=True,
)


def check_database_connection() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def initialize_database() -> None:
    from app.database.models import Base

    Base.metadata.create_all(bind=engine)
