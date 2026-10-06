"""The order API: create_app() builds it; run with `uvicorn --factory mock_api.main:create_app`."""

import random
import time
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from mock_api.chaos import install_chaos
from mock_api.config import DatabaseSettings, Settings
from mock_api.errors import error_body, install_error_handlers
from mock_api.ratelimit import SlidingWindowLimiter
from mock_api.routers import customers, orders, products, returns

OPENAPI_YAML = Path(__file__).parent / "static" / "openapi.yaml"


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    clock: Callable[[], float] = time.monotonic,
    rng: random.Random | None = None,
) -> FastAPI:
    settings = settings or Settings()
    engine = engine or create_engine(DatabaseSettings().url(), pool_pre_ping=True)

    # The client gets the hand-written openapi.yaml; FastAPI's generated docs stay off.
    app = FastAPI(title="Lumora order API", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.clients = settings.clients
    app.state.sessions = sessionmaker(engine, expire_on_commit=False)
    app.state.limiter = SlidingWindowLimiter(
        settings.rate_limit, settings.rate_window_seconds, clock
    )

    install_error_handlers(app)
    install_chaos(app, settings.latency_range, settings.error_rate, rng or random.Random())
    for module in (customers, orders, products, returns):
        app.include_router(module.router)

    @app.get("/health", include_in_schema=False)
    def health() -> JSONResponse:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse(error_body("database_unavailable", "Database unreachable."), 503)
        return JSONResponse({"status": "ok"})

    @app.get("/openapi.yaml", include_in_schema=False)
    def openapi_yaml() -> FileResponse:
        return FileResponse(OPENAPI_YAML, media_type="application/yaml")

    return app
