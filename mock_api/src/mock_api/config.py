"""Runtime configuration for the mock order system."""

from dataclasses import dataclass

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL, make_url

COMMERCE_DB = "lumora_commerce"
SCOPES = frozenset({"read", "write"})


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


@dataclass(frozen=True, slots=True)
class ApiClient:
    name: str
    key: SecretStr
    scopes: frozenset[str]


def parse_api_keys(value: str) -> tuple[ApiClient, ...]:
    """Parse "name:key:scope[+scope],..." into clients, one key per client."""
    clients: list[ApiClient] = []
    for entry in (e.strip() for e in value.split(",")):
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) != 3 or not all(parts):
            raise ValueError(f"API key entry must be name:key:scopes, got {entry.split(':')[0]!r}")
        name, key, scope_list = parts
        scopes = frozenset(scope_list.split("+"))
        if not scopes <= SCOPES:
            raise ValueError(f"Unknown scope for {name!r}: {sorted(scopes - SCOPES)}")
        clients.append(ApiClient(name=name, key=SecretStr(key), scopes=scopes))
    names = [c.name for c in clients]
    keys = [c.key.get_secret_value() for c in clients]
    if len(set(names)) != len(names) or len(set(keys)) != len(keys):
        raise ValueError("API key names and keys must be unique")
    return tuple(clients)


class Settings(BaseSettings):
    """API settings, from MOCK_API_* environment variables or .env."""

    model_config = SettingsConfigDict(env_prefix="MOCK_API_", env_file=".env", extra="ignore")

    # "copilot:<key>:read,admin:<key>:read+write". No keys means every request gets 401.
    keys: str = ""
    rate_limit: int = 100
    rate_window_seconds: float = 60.0
    # Realism flags, off by default: "0", "250" or a range like "50-400" (milliseconds),
    # and the share of requests answered with a random 500/502/503.
    latency_ms: str = "0"
    error_rate: float = 0.0

    @field_validator("keys")
    @classmethod
    def _valid_keys(cls, value: str) -> str:
        parse_api_keys(value)
        return value

    @field_validator("latency_ms")
    @classmethod
    def _valid_latency(cls, value: str) -> str:
        parse_latency(value)
        return value

    @field_validator("error_rate")
    @classmethod
    def _valid_error_rate(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("error_rate must be between 0 and 1")
        return value

    @property
    def clients(self) -> tuple[ApiClient, ...]:
        return parse_api_keys(self.keys)

    @property
    def latency_range(self) -> tuple[float, float]:
        return parse_latency(self.latency_ms)


def parse_latency(value: str) -> tuple[float, float]:
    """(min, max) seconds from "0", "250" or "50-400" milliseconds."""
    low, _, high = value.strip().partition("-")
    try:
        lo, hi = float(low), float(high or low)
    except ValueError:
        raise ValueError(f"latency must be N or MIN-MAX milliseconds, got {value!r}") from None
    if lo < 0 or hi < lo:
        raise ValueError(f"latency range is invalid: {value!r}")
    return lo / 1000, hi / 1000
