"""Engine, sessão e Base declarativa do SQLAlchemy."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    # Descarta conexões que o Postgres possa ter fechado do outro lado.
    # Importante em plano free, onde o banco hiberna por inatividade.
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Base declarativa compartilhada por todos os models."""


def get_db() -> Generator[Session, None, None]:
    """Dependência do FastAPI: entrega uma sessão e garante o fechamento.

    O `finally` roda mesmo se o endpoint levantar exceção, então nenhuma conexão
    fica pendurada no pool por causa de um erro.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
