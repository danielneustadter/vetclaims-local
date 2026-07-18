from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False, "timeout": 30},
)


try:
    import sqlite_vec
except ImportError:  # pragma: no cover
    sqlite_vec = None


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()
    if sqlite_vec is not None:
        dbapi_conn.enable_load_extension(True)
        sqlite_vec.load(dbapi_conn)
        dbapi_conn.enable_load_extension(False)


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


EMBED_DIM = 768  # nomic-embed-text


def init_db() -> None:
    from . import models  # noqa: F401  (register mappings)

    Base.metadata.create_all(engine)
    if sqlite_vec is not None:
        with engine.connect() as conn:
            conn.exec_driver_sql(
                "CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunk USING "
                f"vec0(chunk_id INTEGER PRIMARY KEY, embedding float[{EMBED_DIM}])")
            conn.commit()


def session() -> Session:
    """Plain session for worker threads (caller closes)."""
    return SessionLocal()
