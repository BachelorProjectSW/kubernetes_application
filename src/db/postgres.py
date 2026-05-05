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
    admin_db = os.getenv("POSTGRES_ADMIN_DB", "postgres")
    return url.set(database=admin_db)


def _db_name(url: URL) -> str:
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
    global _ENGINE
    if _ENGINE is None:
        with _ENGINE_LOCK:
            if _ENGINE is None:  # re-check after acquiring lock
                _ENGINE = create_engine(_database_url(), pool_pre_ping=True)
    return _ENGINE


def _ensure_database_exists() -> None:
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
    """Create postgres database and tables when missing."""
    log.info("db.init_database.start")
    _ensure_database_exists()
    SQLModel.metadata.create_all(_engine())
    log.info("db.init_database.done")


def save_config(config: Config) -> None:
    """Persist full Config model content as JSON."""
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
    """Persist a structured log model payload linked to config_id."""
    row = AppLogRecord(
        config_id=config_id,
        log_type=type(log_model).__name__,
        payload_json=log_model.model_dump(mode="json"),
        terminal_debug=None,
    )
    with Session(_engine()) as session:
        session.add(row)
        session.commit()
    log.info("db.save_model_log", config_id=config_id, log_type=type(log_model).__name__)


def save_terminal_debug(config_id: str | None, message: str, level: str, payload: dict[str, Any]) -> None:
    """Save all logs to DB."""
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


def read_model_logs(log_model_class: type[TModel], config_id: str | None = None, since: datetime | None = None) -> list[TModel]:
    """Read model logs from DB and parse as Pydantic objects."""
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
    log.info(
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
    """Return the most recent NodeStatusLog for one node in one cluster."""
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
    """Read a persisted config snapshot by config id."""
    query = select(ConfigRecord).where(ConfigRecord.config_id == config_id)

    with Session(_engine()) as session:
        row = session.exec(query).first()

    if row is None:
        return None

    return Config.model_validate(row.config_json)


def read_config_by_name(config_name: str) -> Config | None:
    """Read the first persisted config snapshot by config name."""
    query = select(ConfigRecord).where(ConfigRecord.config_name == config_name)

    with Session(_engine()) as session:
        row = session.exec(query).first()

    if row is None:
        return None

    return Config.model_validate(row.config_json)


def read_all_configs() -> list[Config]:
    """Read all persisted config snapshots."""
    query = select(ConfigRecord).order_by(ConfigRecord.created_at)

    with Session(_engine()) as session:
        return session.exec(query).all()
