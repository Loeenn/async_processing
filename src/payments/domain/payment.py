from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Self
from uuid import UUID

from payments.domain.events import DomainEvent, PaymentCreated
from payments.domain.exceptions import InvariantViolationError
from payments.domain.value_objects import Money


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass
class Payment:
    """Агрегат платежа: хранит состояние и правила перехода между статусами"""

    payment_id: UUID
    money: Money
    description: str
    metadata: dict[str, Any]
    idempotency_key: str
    webhook_url: str
    status: PaymentStatus
    created_at: datetime
    processed_at: datetime | None = None
    _events: list[DomainEvent] = field(default_factory=list, repr=False)

    @classmethod
    def create(
        cls,
        *,
        payment_id: UUID,
        money: Money,
        description: str,
        metadata: dict[str, Any],
        idempotency_key: str,
        webhook_url: str,
        created_at: datetime,
    ) -> Self:
        payment = cls(
            payment_id=payment_id,
            money=money,
            description=description,
            metadata=metadata,
            idempotency_key=idempotency_key,
            webhook_url=webhook_url,
            status=PaymentStatus.PENDING,
            created_at=created_at,
        )
        payment._events.append(
            PaymentCreated(
                occurred_at=created_at,
                payment_id=payment_id,
                amount=str(money.amount),
                currency=money.currency,
            )
        )
        return payment

    @property
    def is_processed(self) -> bool:
        return self.status is not PaymentStatus.PENDING

    def mark_succeeded(self, processed_at: datetime) -> None:
        self._complete(PaymentStatus.SUCCEEDED, processed_at)

    def mark_failed(self, processed_at: datetime) -> None:
        self._complete(PaymentStatus.FAILED, processed_at)

    def pull_events(self) -> list[DomainEvent]:
        """Отдаёт накопленные события и очищает список"""
        events = list(self._events)
        self._events.clear()
        return events

    def _complete(self, status: PaymentStatus, processed_at: datetime) -> None:
        if self.is_processed:
            message = f"payment {self.payment_id} is already {self.status}"
            raise InvariantViolationError(message)

        self.status = status
        self.processed_at = processed_at
