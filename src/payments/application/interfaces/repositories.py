from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from payments.application.dto import OutboxMessage
from payments.domain.events import DomainEvent
from payments.domain.payment import Payment


class IPaymentRepository(ABC):
    @abstractmethod
    async def add(self, payment: Payment) -> None: ...

    @abstractmethod
    async def get(self, payment_id: UUID) -> Payment | None: ...

    @abstractmethod
    async def find_by_idempotency_key(self, idempotency_key: str) -> Payment | None: ...

    @abstractmethod
    async def save_processing_result(self, payment: Payment) -> bool:
        """Сохраняет результат обработки

        возвращает False, если платёж уже успел получить финальный статус -
        значит, его обработал другой consumer
        """


class IOutboxRepository(ABC):
    @abstractmethod
    async def add(self, events: Sequence[DomainEvent]) -> None: ...

    @abstractmethod
    async def fetch_unpublished(self, limit: int) -> Sequence[OutboxMessage]: ...

    @abstractmethod
    async def mark_published(
        self, event_ids: Sequence[UUID], published_at: datetime
    ) -> None: ...
