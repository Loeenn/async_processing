from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from payments.application.dto import OutboxMessage
from payments.application.interfaces.repositories import (
    IOutboxRepository,
    IPaymentRepository,
)
from payments.domain.events import DomainEvent
from payments.domain.payment import Payment, PaymentStatus
from payments.infrastructure.database.mappers import OutboxMapper, PaymentMapper
from payments.infrastructure.database.models import OutboxModel, PaymentModel


class PaymentRepository(IPaymentRepository):
    def __init__(self, session: AsyncSession, mapper: PaymentMapper) -> None:
        self._session = session
        self._mapper = mapper

    async def add(self, payment: Payment) -> None:
        self._session.add(self._mapper.to_model(payment))

    async def get(self, payment_id: UUID) -> Payment | None:
        model = await self._session.get(PaymentModel, payment_id)
        return self._mapper.to_entity(model) if model else None

    async def find_by_idempotency_key(self, idempotency_key: str) -> Payment | None:
        query = select(PaymentModel).where(
            PaymentModel.idempotency_key == idempotency_key
        )
        model = (await self._session.scalars(query)).first()
        return self._mapper.to_entity(model) if model else None

    async def save_processing_result(self, payment: Payment) -> bool:
        # Условие status = pending делает обновление идемпотентным: если платёж
        # уже обработан другим consumer'ом, апдейт не заденет ни одной строки
        statement = (
            update(PaymentModel)
            .where(
                PaymentModel.payment_id == payment.payment_id,
                PaymentModel.status == PaymentStatus.PENDING,
            )
            .values(status=payment.status, processed_at=payment.processed_at)
            .returning(PaymentModel.payment_id)
        )
        updated = (await self._session.scalars(statement)).first()
        return updated is not None


class OutboxRepository(IOutboxRepository):
    def __init__(self, session: AsyncSession, mapper: OutboxMapper) -> None:
        self._session = session
        self._mapper = mapper

    async def add(self, events: Sequence[DomainEvent]) -> None:
        if not events:
            return

        self._session.add_all([self._mapper.to_model(event) for event in events])

    async def fetch_unpublished(self, limit: int) -> Sequence[OutboxMessage]:
        # SKIP LOCKED позволяет запустить несколько релеев: они разберут разные
        # строки и не будут ждать друг друга на блокировках
        query = (
            select(OutboxModel)
            .where(OutboxModel.published_at.is_(None))
            .order_by(OutboxModel.occurred_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        models = (await self._session.scalars(query)).all()
        return [self._mapper.to_message(model) for model in models]

    async def mark_published(
        self, event_ids: Sequence[UUID], published_at: datetime
    ) -> None:
        if not event_ids:
            return

        statement = (
            update(OutboxModel)
            .where(OutboxModel.event_id.in_(event_ids))
            .values(published_at=published_at)
        )
        await self._session.execute(statement)
