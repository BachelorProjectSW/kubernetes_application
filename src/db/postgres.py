from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Any, TypeVar
import structlog

from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder
from sqlalchemy import JSON, Column, Text, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlmodel import Field, SQLModel, Session, select

from ..custom_logging.models.log_models import (
    NodeStatusLog,
)
from ..models.basemodels import Config

TModel = TypeVar("TModel", bound=BaseModel)
log = structlog.get_logger()


def _database_url() -> str:
    """Build the database connection URL from environment variables.

    Uses `DATABASE_URL` directly when present. Otherwise builds a URL from
    individual `POSTGRES_*` environment variables with project defaults.

    Returns:
        Full SQLAlchemy/PostgreSQL connection URL.

    """
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    host = os.getenv("POSTGRES_HOST", "100.109.95.2")  # Strato IP
    port = os.getenv("POSTGRES_PORT", "5433")
    user = os.getenv("POSTGRES_USER", "strato")
    password = os.getenv("POSTGRES_PASSWORD", "strato")
    db_name = os.getenv("POSTGRES_DB", "strato")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db_name}"


def _admin_url(url: URL) -> URL:
    """Create an admin-database URL used for database creation checks.

    Args:
        url: Parsed application database URL.

    Returns:
        URL pointing to the admin database (usually `postgres`).

    """
    admin_db = os.getenv("POSTGRES_ADMIN_DB", "postgres")
    return url.set(database=admin_db)


def _db_name(url: URL) -> str:
    """Extract the database name from a parsed URL.

    Args:
        url: Parsed database URL.

    Returns:
        Database name from the URL.

    Raises:
        ValueError: If the URL has no database component.

    """
    if not url.database:
        raise ValueError("DATABASE_URL must include a database name")
    return url.database


class ConfigRecord(SQLModel, table=True):
    """Persisted configuration snapshot row."""

    __tablename__ = "configs"

    id: int | None = Field(default=None, primary_key=True)
    config_id: str = Field(index=True)
    config_name: str | None = Field(default=None, index=True)
    config_json: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)


class AppLogRecord(SQLModel, table=True):
    """Persisted log row for structured and terminal log payloads."""

    __tablename__ = "app_logs"

    id: int | None = Field(default=None, primary_key=True)
    config_id: str | None = Field(default=None, index=True)
    log_type: str = Field(index=True)
    payload_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    terminal_debug: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)


_ENGINE = None
_ENGINE_LOCK = threading.Lock()


def _engine():
    """Return the shared SQLAlchemy database engine.

    The engine is the main object used to talk to the database. It manages
    database connections for the whole application and reuses them instead
    of creating a new connection every time.

    It is created only once (the first time this function is called) and then
    reused for all future database operations to improve performance.

    A lock is used to make sure the engine is not created multiple times if
    several parts of the program try to initialize it at the same time.

    Returns:
        The shared SQLAlchemy engine used for all database access.

    """
    global _ENGINE
    if _ENGINE is None:
        with _ENGINE_LOCK:
            if _ENGINE is None:  # re-check after acquiring lock
                _ENGINE = create_engine(_database_url(), pool_pre_ping=True)
    return _ENGINE


def _ensure_database_exists() -> None:
    """Ensure the target PostgreSQL database exists before table creation.

    Connects to the admin database, checks whether the configured application
    database is present, and creates it when missing.
    """
    url = make_url(_database_url())
    database_name = _db_name(url)
    admin_engine = create_engine(_admin_url(url), isolation_level="AUTOCOMMIT", pool_pre_ping=True)

    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": database_name},
        ).scalar_one_or_none()

        if exists is None:
            conn.execute(text(f'CREATE DATABASE "{database_name}"'))


def init_database() -> None:
    """Initialize database infrastructure required by the application.

    Ensures the database exists and creates all SQLModel tables if they are
    missing. Safe to call on startup.
    """
    log.info("db.init_database.start")
    _ensure_database_exists()
    SQLModel.metadata.create_all(_engine())
    log.info("db.init_database.done")


def save_config(config: Config) -> None:
    """Save a full configuration snapshot to the database.

    Args:
        config: In-memory configuration object to persist.

    """
    payload = config.model_dump(mode="python")
    row = ConfigRecord(
        config_id=config.id,
        config_name=config.name,
        config_json=payload,
    )
    with Session(_engine()) as session:
        session.add(row)
        session.commit()
    log.info("db.save_config", config_id=config.id, config_name=config.name)


def save_model_log(config_id: str | None, log_model: BaseModel) -> None:
    """Save a structured log model as a JSON payload.

    Args:
        config_id: Optional configuration ID used to group logs by test run.
        log_model: Pydantic model instance representing one log entry.

    """
    row = AppLogRecord(
        config_id=config_id,
        log_type=type(log_model).__name__,
        payload_json=log_model.model_dump(mode="json"),
        terminal_debug=None,
    )
    with Session(_engine()) as session:
        session.add(row)
        session.commit()
    log.debug("db.save_model_log", config_id=config_id, log_type=type(log_model).__name__)


def save_terminal_debug(config_id: str | None, message: str, level: str, payload: dict[str, Any]) -> None:
    """Save a terminal/debug log entry.

    Args:
        config_id: Optional configuration ID used to group debug logs.
        message: Human-readable log message.
        level: Log level (for example `info`, `warning`, `error`).
        payload: Structured context data to store with the message.

    """
    safe_payload = jsonable_encoder(payload)
    row = AppLogRecord(
        config_id=config_id,
        log_type=level,
        payload_json=safe_payload,
        terminal_debug=message,
    )
    with Session(_engine()) as session:
        session.add(row)
        session.commit()


def read_model_logs(
        log_model_class: type[TModel],
        config_id: str | None = None,
        since: datetime | None = None
    ) -> list[TModel]:
    """Read structured logs and parse them into a given Pydantic model.

    Args:
        log_model_class: Model class used to parse stored JSON payloads.
        config_id: Optional configuration ID filter.
        since: Optional lower bound for `created_at` timestamp.

    Returns:
        Parsed log entries ordered by creation time.

    """
    query = select(AppLogRecord).where(AppLogRecord.log_type == log_model_class.__name__)
    if config_id is not None:
        query = query.where(AppLogRecord.config_id == config_id)
    if since is not None:
        query = query.where(AppLogRecord.created_at >= since)
    query = query.order_by(AppLogRecord.created_at)

    with Session(_engine()) as session:
        rows = session.exec(query).all()

    logs: list[TModel] = []
    for row in rows:
        if row.payload_json is None:
            continue
        logs.append(log_model_class(**row.payload_json))
    log.debug(
        "db.read_model_logs",
        config_id=config_id,
        log_type=log_model_class.__name__,
        count=len(logs),
    )
    return logs


def read_latest_node_status_log(
    config_id: str,
    cluster_name: str,
    node_name: str,
) -> NodeStatusLog | None:
    """Read the latest node-status entry for a specific node.

    Args:
        config_id: Configuration ID used to scope the query.
        cluster_name: Cluster name that owns the node.
        node_name: Node name to search for.

    Returns:
        Latest matching `NodeStatusLog`, or `None` if not found.

    """
    query = select(AppLogRecord).where(AppLogRecord.log_type == NodeStatusLog.__name__)
    query = query.where(AppLogRecord.config_id == config_id)
    query = query.order_by(AppLogRecord.created_at.desc())

    with Session(_engine()) as session:
        rows = session.exec(query).all()

    for row in rows:
        if row.payload_json is None:
            continue
        try:
            entry = NodeStatusLog(**row.payload_json)
        except Exception:
            continue
        if entry.cluster == cluster_name and entry.node == node_name:
            log.info(
                "db.read_latest_node_status_log",
                config_id=config_id,
                cluster_name=cluster_name,
                node_name=node_name,
            )
            return entry

    log.info(
        "db.read_latest_node_status_log",
        config_id=config_id,
        cluster_name=cluster_name,
        node_name=node_name,
        found=False,
    )
    return None


def read_config_by_id(config_id: str) -> Config | None:
    """Load a configuration snapshot by configuration ID.

    Args:
        config_id: Configuration ID to lookup.

    Returns:
        Parsed `Config` object, or `None` when no matching row exists.

    """
    query = select(ConfigRecord).where(ConfigRecord.config_id == config_id)

    with Session(_engine()) as session:
        row = session.exec(query).first()

    if row is None:
        return None

    return Config.model_validate(row.config_json)


def read_config_by_name(config_name: str) -> Config | None:
    """Load the first configuration snapshot that matches a config name.

    Args:
        config_name: Human-readable configuration name.

    Returns:
        Parsed `Config` object, or `None` when no matching row exists.

    """
    query = select(ConfigRecord).where(ConfigRecord.config_name == config_name)

    with Session(_engine()) as session:
        row = session.exec(query).first()

    if row is None:
        return None

    return Config.model_validate(row.config_json)


def read_all_configs() -> list[Config]:
    """Read all saved configuration rows in creation order.

    Returns:
        List of persisted configuration rows ordered by `created_at`.

    """
    query = select(ConfigRecord).order_by(ConfigRecord.created_at)

    with Session(_engine()) as session:
        return session.exec(query).all()
