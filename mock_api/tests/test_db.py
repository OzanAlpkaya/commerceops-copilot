from sqlalchemy import Engine, text

from mock_api.config import DatabaseSettings


def test_test_database_is_reachable(db_engine: Engine) -> None:
    with db_engine.connect() as conn:
        assert (
            conn.execute(text("SELECT current_database()")).scalar_one() == "lumora_commerce_test"
        )


def test_url_follows_postgres_port(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "db.internal")
    monkeypatch.setenv("POSTGRES_PORT", "5434")
    monkeypatch.delenv("MOCK_API_DATABASE_URL", raising=False)

    url = DatabaseSettings(_env_file=None).url()  # type: ignore[call-arg]

    assert (url.host, url.port, url.database) == ("db.internal", 5434, "lumora_commerce")


def test_explicit_url_wins(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_PORT", "5434")
    monkeypatch.setenv("MOCK_API_DATABASE_URL", "postgresql+psycopg://u:p@db:5432/lumora_commerce")

    url = DatabaseSettings(_env_file=None).url()  # type: ignore[call-arg]

    assert (url.host, url.port) == ("db", 5432)
