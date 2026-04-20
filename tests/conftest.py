from __future__ import annotations

import os
import sys
from pathlib import Path

# Redirect DB to a test-only file BEFORE any import triggers get_settings() caching,
# so tests never touch the real instance/app.db.
os.environ["DB_PATH"] = "instance/test.db"

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from services.signing_service import ensure_keypair
from utils.db_utils import ensure_runtime_directories, get_db_connection, init_db


@pytest.fixture(autouse=True)
def clean_database() -> None:
    ensure_runtime_directories()
    init_db()
    ensure_keypair()
    with get_db_connection() as connection:
        connection.execute("DELETE FROM parser_runs")
        connection.execute("DELETE FROM proofs")
        connection.execute("DELETE FROM captures")
        connection.commit()
    yield


@pytest.fixture()
def client():
    app = create_app({"TESTING": True})
    with app.test_client() as test_client:
        yield test_client
