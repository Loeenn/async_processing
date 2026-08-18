from datetime import datetime
from decimal import Decimal
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from payments.application.dto import PaymentView
from payments.domain.value_objects import Currency


class CreatePaymentRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: Currency
    description: str = Field(default="", max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    webhook_url: HttpUrl


class CreatePaymentResponse(BaseModel):
    payment_id: UUID
    status: str
    created_at: datetime

    @classmethod
    def from_view(cls, view: PaymentView) -> Self:
        return cls(
            payment_id=view.payment_id,
            status=view.status,
            created_at=view.created_at,
        )


class PaymentResponse(BaseModel):
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
    def from_view(cls, view: PaymentView) -> Self:
        return cls(
            payment_id=view.payment_id,
            amount=view.amount,
            currency=view.currency,
            description=view.description,
            metadata=view.metadata,
            status=view.status,
            idempotency_key=view.idempotency_key,
            webhook_url=view.webhook_url,
            created_at=view.created_at,
            processed_at=view.processed_at,
        )
