from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from bootstrap.config import AppConfig
from bootstrap.containers import build_api_container
from bootstrap.logging import setup_logging
from payments.presentation.http.auth import build_api_key_guard
from payments.presentation.http.routers import (
    build_health_router,
    build_payments_router,
)


def build_app() -> FastAPI:
    config = AppConfig.load()
    setup_logging(config.log_level)
    container = build_api_container(config)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await container.shutdown()

    app = FastAPI(title="Payments API", version="0.1.0", lifespan=lifespan)
    app.include_router(build_health_router())
    app.include_router(
        build_payments_router(container.create_payment, container.get_payment),
        prefix="/api/v1/payments",
        tags=["payments"],
        dependencies=[Depends(build_api_key_guard(config.api_key))],
    )

    return app


app = build_app()
