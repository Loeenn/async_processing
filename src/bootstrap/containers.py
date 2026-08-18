"""Композиционный корень: единственное место, где абстракции связываются
с конкретными реализациями, остальные слои знают только про интерфейсы
"""

import logging
from dataclasses import dataclass

import httpx
from faststream.rabbit import RabbitBroker
from sqlalchemy.ext.asyncio import AsyncEngine

from bootstrap.config import AppConfig
from payments.application.interfaces.ports import IIdGenerator
from payments.application.interfaces.unit_of_work import IUnitOfWorkFactory
from payments.application.interfaces.use_cases import (
    ICreatePaymentUseCase,
    IGetPaymentUseCase,
    IProcessPaymentUseCase,
    IPublishOutboxEventsUseCase,
)
from payments.application.use_cases.create_payment import CreatePaymentUseCase
from payments.application.use_cases.get_payment import GetPaymentUseCase
from payments.application.use_cases.process_payment import ProcessPaymentUseCase
from payments.application.use_cases.publish_outbox_events import (
    PublishOutboxEventsUseCase,
)
from payments.infrastructure.database.engine import create_engine, create_session_maker
from payments.infrastructure.database.mappers import OutboxMapper, PaymentMapper
from payments.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWorkFactory
from payments.infrastructure.gateway.emulated import EmulatedPaymentGateway
from payments.infrastructure.messaging.publisher import RabbitEventPublisher
from payments.infrastructure.messaging.topology import PAYMENTS_EXCHANGE, ROUTING_KEYS
from payments.infrastructure.services.clock import SystemClock
from payments.infrastructure.services.id_generator import UuidGenerator
from payments.infrastructure.webhooks.http_sender import HttpWebhookSender


@dataclass(frozen=True)
class ApiContainer:
    config: AppConfig
    engine: AsyncEngine
    create_payment: ICreatePaymentUseCase
    get_payment: IGetPaymentUseCase

    async def shutdown(self) -> None:
        await self.engine.dispose()


@dataclass(frozen=True)
class ConsumerContainer:
    config: AppConfig
    engine: AsyncEngine
    broker: RabbitBroker
    http_client: httpx.AsyncClient
    process_payment: IProcessPaymentUseCase

    async def shutdown(self) -> None:
        await self.http_client.aclose()
        await self.engine.dispose()


@dataclass(frozen=True)
class OutboxContainer:
    config: AppConfig
    engine: AsyncEngine
    broker: RabbitBroker
    publish_events: IPublishOutboxEventsUseCase

    async def shutdown(self) -> None:
        await self.broker.stop()
        await self.engine.dispose()


def build_api_container(config: AppConfig) -> ApiContainer:
    engine = create_engine(config.db)
    uow_factory = _build_uow_factory(engine, UuidGenerator())

    return ApiContainer(
        config=config,
        engine=engine,
        create_payment=CreatePaymentUseCase(
            uow_factory, SystemClock(), UuidGenerator()
        ),
        get_payment=GetPaymentUseCase(uow_factory),
    )


def build_consumer_container(config: AppConfig) -> ConsumerContainer:
    engine = create_engine(config.db)
    uow_factory = _build_uow_factory(engine, UuidGenerator())
    http_client = httpx.AsyncClient(timeout=config.webhook.timeout)

    process_payment = ProcessPaymentUseCase(
        uow_factory=uow_factory,
        gateway=EmulatedPaymentGateway(config.gateway),
        webhook_sender=HttpWebhookSender(
            http_client, config.webhook, logging.getLogger("payments.webhooks")
        ),
        clock=SystemClock(),
        logger=logging.getLogger("payments.consumer"),
    )

    return ConsumerContainer(
        config=config,
        engine=engine,
        broker=RabbitBroker(config.rabbit.url),
        http_client=http_client,
        process_payment=process_payment,
    )


def build_outbox_container(config: AppConfig) -> OutboxContainer:
    engine = create_engine(config.db)
    uow_factory = _build_uow_factory(engine, UuidGenerator())
    broker = RabbitBroker(config.rabbit.url)

    publish_events = PublishOutboxEventsUseCase(
        uow_factory=uow_factory,
        publisher=RabbitEventPublisher(broker, PAYMENTS_EXCHANGE),
        clock=SystemClock(),
        batch_size=config.outbox.batch_size,
    )

    return OutboxContainer(
        config=config,
        engine=engine,
        broker=broker,
        publish_events=publish_events,
    )


def _build_uow_factory(
    engine: AsyncEngine, id_generator: IIdGenerator
) -> IUnitOfWorkFactory:
    return SqlAlchemyUnitOfWorkFactory(
        session_maker=create_session_maker(engine),
        payment_mapper=PaymentMapper(),
        outbox_mapper=OutboxMapper(id_generator, ROUTING_KEYS),
    )
