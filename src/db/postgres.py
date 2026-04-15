from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel
from sqlalchemy import JSON, Column, Text, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlmodel import Field, SQLModel, Session

from ..models.basemodels import Config


def _database_url() -> str:
	url = os.getenv("DATABASE_URL")
	if url:
		return url

	host = os.getenv("POSTGRES_HOST", "localhost")
	port = os.getenv("POSTGRES_PORT", "5432")
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
	__tablename__ = "configs"

	id: int | None = Field(default=None, primary_key=True)
	config_id: str = Field(index=True)
	config_name: str | None = Field(default=None, index=True)
	config_json: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
	created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)


class AppLogRecord(SQLModel, table=True):
	__tablename__ = "app_logs"

	id: int | None = Field(default=None, primary_key=True)
	config_id: str | None = Field(default=None, index=True)
	log_type: str = Field(index=True)
	payload_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
	terminal_debug: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
	created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)


_ENGINE = None


def _engine():
	global _ENGINE
	if _ENGINE is None:
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
	_ensure_database_exists()
	SQLModel.metadata.create_all(_engine())


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


def save_model_log(config_id: str | None, log_model: BaseModel) -> None:
	"""Persist a structured log model payload linked to config_id."""
	row = AppLogRecord(
		config_id=config_id,
		log_type=type(log_model).__name__,
		payload_json=log_model.model_dump(mode="python"),
		terminal_debug=None,
	)
	with Session(_engine()) as session:
		session.add(row)
		session.commit()


def save_terminal_debug(config_id: str | None, message: str, payload: dict[str, Any] | None = None) -> None:
	"""Persist raw terminal debug text linked to config_id."""
	row = AppLogRecord(
		config_id=config_id,
		log_type="terminal_debug",
		payload_json=payload,
		terminal_debug=message,
	)
	with Session(_engine()) as session:
		session.add(row)
		session.commit()

