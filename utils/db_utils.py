from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class Settings:
    app_host: str
    app_port: int
    db_path: str
    default_expires_days: int
    parser_version: str


def project_path(*parts: str) -> Path:
    return ROOT_DIR.joinpath(*parts)


def _load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    env_values = _load_dotenv(project_path(".env"))

    def _get(name: str, default: str) -> str:
        return os.environ.get(name, env_values.get(name, default))

    return Settings(
        app_host=_get("APP_HOST", "127.0.0.1"),
        app_port=int(_get("APP_PORT", "5000")),
        db_path=_get("DB_PATH", "instance/app.db"),
        default_expires_days=int(_get("DEFAULT_EXPIRES_DAYS", "30")),
        parser_version=_get("PARSER_VERSION", "mercari_parser_v0"),
    )


def reset_settings_cache() -> None:
    get_settings.cache_clear()


def get_db_path() -> Path:
    raw_path = Path(get_settings().db_path)
    if raw_path.is_absolute():
        return raw_path
    return project_path(*raw_path.parts)


def ensure_runtime_directories() -> None:
    directories = (
        project_path("instance"),
        project_path("keys"),
        project_path("captures"),
        project_path("captures", "html"),
        project_path("captures", "text"),
        project_path("captures", "screenshots"),
        project_path("tests", "fixtures"),
    )
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def get_db_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    ensure_runtime_directories()
    schema_path = project_path("schema.sql")
    with get_db_connection() as connection:
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        connection.commit()


def now_jst_iso() -> str:
    return datetime.now(JST).replace(microsecond=0).isoformat()
