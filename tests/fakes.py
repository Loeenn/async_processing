"""Заглушки для юнит-тестов: заменяют БД, брокер, шлюз и часы"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from typing import Any, Self
from uuid import UUID, uuid4

from payments.application.dto import OutboxMessage, WebhookNotification
from payments.application.exceptions import DuplicateIdempotencyKeyError
from payments.application.interfaces.ports import (
    GatewayResult,
    IClock,
    IEventPublisher,
    IIdGenerator,
    IPaymentGateway,
    IWebhookSender,
)
from payments.application.interfaces.repositories import (
    IOutboxRepository,
    IPaymentRepository,
)
from payments.application.interfaces.unit_of_work import IUnitOfWork, IUnitOfWorkFactory
from payments.domain.events import DomainEvent
from payments.domain.payment import Payment, PaymentStatus
from payments.domain.value_objects import Currency, Money


@dataclass
class OutboxRecord:
    event_id: UUID
    routing_key: str
    payload: dict[str, Any]
    published_at: datetime | None = None


@dataclass
class Storage:
    """Хранилище в памяти вместо PostgreSQL"""

    payments: dict[UUID, Payment] = field(default_factory=dict)
    outbox: list[OutboxRecord] = field(default_factory=list)

    # Имитация гонки: на commit срабатывает уникальный индекс, а платёж
    # конкурента появляется в хранилище
    duplicate_on_commit: bool = False
    competitor: Payment | None = None


class FakePaymentRepository(IPaymentRepository):
    def __init__(self, storage: Storage, staged: list[Payment]) -> None:
        self._storage = storage
        self._staged = staged

    async def add(self, payment: Payment) -> None:
        self._staged.append(payment)

    async def get(self, payment_id: UUID) -> Payment | None:
        return self._storage.payments.get(payment_id)

    async def find_by_idempotency_key(self, idempotency_key: str) -> Payment | None:
        for payment in self._storage.payments.values():
            if payment.idempotency_key == idempotency_key:
                return payment
        return None

    async def save_processing_result(self, payment: Payment) -> bool:
        stored = self._storage.payments.get(payment.payment_id)
        if stored is not None and stored is not payment and stored.is_processed:
            return False

        self._storage.payments[payment.payment_id] = payment
        return True


class FakeOutboxRepository(IOutboxRepository):
    def __init__(self, storage: Storage, staged: list[OutboxRecord]) -> None:
        self._storage = storage
        self._staged = staged

    async def add(self, events: Sequence[DomainEvent]) -> None:
        for event in events:
            self._staged.append(
                OutboxRecord(
                    event_id=uuid4(),
                    routing_key=event.event_type,
                    payload=event.to_payload(),
                )
            )

    async def fetch_unpublished(self, limit: int) -> Sequence[OutboxMessage]:
        records = [r for r in self._storage.outbox if r.published_at is None]
        return [
            OutboxMessage(
                event_id=r.event_id, routing_key=r.routing_key, payload=r.payload
            )
            for r in records[:limit]
        ]

    async def mark_published(
        self, event_ids: Sequence[UUID], published_at: datetime
    ) -> None:
        for record in self._storage.outbox:
            if record.event_id in event_ids:
                record.published_at = published_at


class FakeUnitOfWork(IUnitOfWork):
    """Новые записи попадают в хранилище только после commit"""

    def __init__(self, storage: Storage) -> None:
        self._storage = storage
        self._staged_payments: list[Payment] = []
        self._staged_events: list[OutboxRecord] = []
        self._payments = FakePaymentRepository(storage, self._staged_payments)
        self._outbox = FakeOutboxRepository(storage, self._staged_events)

    @property
    def payments(self) -> IPaymentRepository:
        return self._payments

    @property
    def outbox(self) -> IOutboxRepository:
        return self._outbox

    async def commit(self) -> None:
        if self._storage.duplicate_on_commit:
            if self._storage.competitor is not None:
                competitor = self._storage.competitor
                self._storage.payments[competitor.payment_id] = competitor
            await self.rollback()
            raise DuplicateIdempotencyKeyError

        for payment in self._staged_payments:
            self._storage.payments[payment.payment_id] = payment
        self._storage.outbox.extend(self._staged_events)
        await self.rollback()

    async def rollback(self) -> None:
        self._staged_payments.clear()
        self._staged_events.clear()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.rollback()


class FakeUnitOfWorkFactory(IUnitOfWorkFactory):
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def create(self) -> IUnitOfWork:
        return FakeUnitOfWork(self.storage)


class FakeGateway(IPaymentGateway):
    def __init__(self, result: GatewayResult) -> None:
        self.result = result
        self.calls = 0

    async def process(self, money: Money) -> GatewayResult:
        self.calls += 1
        return self.result


class FakeWebhookSender(IWebhookSender):
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.sent: list[WebhookNotification] = []

    async def send(self, notification: WebhookNotification) -> None:
        self.sent.append(notification)
        if self.error is not None:
            raise self.error


class FakePublisher(IEventPublisher):
    def __init__(self) -> None:
        self.published: list[OutboxMessage] = []

    async def publish(self, message: OutboxMessage) -> None:
        self.published.append(message)


class FakeClock(IClock):
    def __init__(self, moment: datetime | None = None) -> None:
        self.moment = moment or datetime(2026, 8, 18, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.moment


class FakeIdGenerator(IIdGenerator):
    def __init__(self, *ids: UUID) -> None:
        self._ids = list(ids)

    def generate(self) -> UUID:
        return self._ids.pop(0) if self._ids else uuid4()


def make_payment(
    status: PaymentStatus = PaymentStatus.PENDING,
    idempotency_key: str = "key",
    payment_id: UUID | None = None,
) -> Payment:
    payment = Payment.create(
        payment_id=payment_id or uuid4(),
        money=Money(amount=Decimal("100.00"), currency=Currency.RUB),
        description="test",
        metadata={},
        idempotency_key=idempotency_key,
        webhook_url="https://example.com/hook",
        created_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
    )
    payment.pull_events()

    if status is not PaymentStatus.PENDING:
        payment.status = status
        payment.processed_at = datetime(2026, 8, 18, 12, 0, 5, tzinfo=UTC)

    return payment
