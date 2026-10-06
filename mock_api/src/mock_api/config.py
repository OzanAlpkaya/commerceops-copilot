"""Runtime configuration for the mock order system."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL, make_url

COMMERCE_DB = "lumora_commerce"


class DatabaseSettings(BaseSettings):
    """Where the lumora_commerce database lives.

    MOCK_API_DATABASE_URL wins when set (docker compose sets it to db:5432). Otherwise the
    URL is built from the same POSTGRES_* variables docker compose reads, so host-side tools
    follow POSTGRES_HOST and POSTGRES_PORT from .env. The defaults mirror the compose file.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str = "commerceops"
    postgres_password: SecretStr = SecretStr("commerceops")
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    mock_api_database_url: str | None = None

    def url(self) -> URL:
        if self.mock_api_database_url:
            return make_url(self.mock_api_database_url)
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=COMMERCE_DB,
        )
