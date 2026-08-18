import asyncio

from faststream import FastStream

from bootstrap.config import AppConfig
from bootstrap.containers import build_consumer_container
from bootstrap.logging import setup_logging
from payments.infrastructure.messaging.topology import declare_topology
from payments.presentation.rabbitmq.routers import build_payments_router


def build_consumer_app() -> FastStream:
    config = AppConfig.load()
    setup_logging(config.log_level)
    container = build_consumer_container(config)

    broker = container.broker
    broker.include_router(
        build_payments_router(container.process_payment, config.consumer.prefetch_count)
    )

    app = FastStream(broker)

    @app.after_startup
    async def declare() -> None:
        await declare_topology(broker)

    @app.on_shutdown
    async def shutdown() -> None:
        await container.shutdown()

    return app


app = build_consumer_app()


def main() -> None:
    asyncio.run(app.run())


if __name__ == "__main__":
    main()
