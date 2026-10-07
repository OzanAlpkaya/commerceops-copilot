"""Shared fixtures. Tests that need Postgres use the compose database server.

The tests get their own database (lumora_commerce_test), created and dropped per session,
so they never touch the seeded lumora_commerce. Host and port come from TEST_DATABASE_URL,
or from the POSTGRES_* variables in the environment or .env (the same ones compose reads).
"""

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import URL, Engine, create_engine, make_url, text
from sqlalchemy.exc import OperationalError

from mock_api.config import DatabaseSettings

TEST_DB = "lumora_commerce_test"


def database_url_for_tests() -> URL:
    # MOCK_API_DATABASE_URL is ignored on purpose: tests only follow the test settings.
    override = os.environ.get("TEST_DATABASE_URL")
    url = make_url(override) if override else DatabaseSettings(mock_api_database_url=None).url()
    return url.set(database=TEST_DB)


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    url = database_url_for_tests()
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))
            conn.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
    except OperationalError as e:
        admin.dispose()
        pytest.fail(
            f"Cannot reach the test Postgres at {url.host}:{url.port} ({e.orig}). "
            "Start it with `make up`, or set TEST_DATABASE_URL.",
            pytrace=False,
        )

    engine = create_engine(url)
    yield engine
    engine.dispose()
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))
    admin.dispose()
