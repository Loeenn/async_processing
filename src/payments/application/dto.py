from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Self
from uuid import UUID

from payments.domain.payment import Payment
from payments.domain.value_objects import Currency


@dataclass(frozen=True)
class CreatePaymentCommand:
    idempotency_key: str
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict[str, Any]
    webhook_url: str


@dataclass(frozen=True)
class PaymentView:
    """Плоское представление платежа для слоя представления"""

    payment_id: UUID
    amount: Decimal
    currency: str
    description: str
    metadata: dict[str, Any]
    status: str
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None

    @classmethod
    def from_entity(cls, payment: Payment) -> Self:
        return cls(
            payment_id=payment.payment_id,
            amount=payment.money.amount,
            currency=payment.money.currency,
            description=payment.description,
            metadata=payment.metadata,
            status=payment.status,
            idempotency_key=payment.idempotency_key,
            webhook_url=payment.webhook_url,
            created_at=payment.created_at,
            processed_at=payment.processed_at,
        )


@dataclass(frozen=True)
class OutboxMessage:
    """Событие из таблицы outbox, готовое к публикации в брокер"""

    event_id: UUID
    routing_key: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class WebhookNotification:
    url: str
    payload: dict[str, Any]
