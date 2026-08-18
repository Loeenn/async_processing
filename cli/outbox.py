import asyncio
import contextlib
import logging
import signal

from bootstrap.config import AppConfig
from bootstrap.containers import build_outbox_container
from bootstrap.logging import setup_logging
from payments.application.interfaces.use_cases import IPublishOutboxEventsUseCase
from payments.infrastructure.messaging.topology import declare_topology


logger = logging.getLogger("payments.outbox")


async def run_relay() -> None:
    """Периодически публикует накопившиеся события из outbox"""
    config = AppConfig.load()
    setup_logging(config.log_level)
    container = build_outbox_container(config)

    await container.broker.connect()
    await declare_topology(container.broker)

    stop = _stop_event()
    logger.info("outbox relay started")

    try:
        while not stop.is_set():
            published = await _publish_batch(container.publish_events)
            if published:
                logger.info("published %s event(s)", published)
                continue

            # Ждём либо следующий тик, либо сигнал остановки
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), config.outbox.poll_interval)
    finally:
        await container.shutdown()
        logger.info("outbox relay stopped")


async def _publish_batch(use_case: IPublishOutboxEventsUseCase) -> int:
    try:
        return await use_case.execute()
    except Exception:
        # Брокер или БД недоступны - события останутся в таблице и уедут позже
        logger.exception("outbox iteration failed")
        return 0


def _stop_event() -> asyncio.Event:
    """Событие, которое взводится по SIGINT/SIGTERM - для graceful shutdown"""
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    return stop


def main() -> None:
    asyncio.run(run_relay())


if __name__ == "__main__":
    main()
