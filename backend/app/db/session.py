from typing import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# Initialize SQLAlchemy engine with MySQL pool settings
engine = create_engine(
    settings.sqlalchemy_database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DEBUG
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# Row isolation plumbing (migration 009)
#
# The owned views read @app_user_id, which is a *connection-level* variable. A pooled
# connection can be handed to a different request, and a session may move to a different
# connection after a commit. Two rules keep the identity correct:
#   1. a connection leaving the pool is cleared, so no request inherits another user's id
#   2. every new transaction re-applies the identity recorded on its session
# ---------------------------------------------------------------------------

@event.listens_for(engine, "checkout")
def _clear_app_user_on_checkout(dbapi_connection, connection_record, connection_proxy):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SET @app_user_id = NULL")
    finally:
        cursor.close()


@event.listens_for(Session, "after_begin")
def _apply_app_user_on_begin(session, transaction, connection):
    app_user_id = session.info.get("app_user_id")
    if app_user_id is not None:
        connection.execute(text("SET @app_user_id = :uid"), {"uid": app_user_id})


def set_app_user(session: Session, user_id: int) -> None:
    """Bind a user identity to this session: applied now, and again at every new transaction."""
    session.info["app_user_id"] = user_id
    session.execute(text("SET @app_user_id = :uid"), {"uid": user_id})


def get_db() -> Generator[Session, None, None]:
    """Dependency generator that yields a database session per API request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
