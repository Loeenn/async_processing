from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class DomainEvent(ABC):
    """Факт, который уже случился в домене

    идентификатор события и способ доставки - забота инфраструктуры, домен
    описывает только сам факт
    """

    occurred_at: datetime

    @property
    @abstractmethod
    def event_type(self) -> str: ...

    @property
    @abstractmethod
    def aggregate_id(self) -> UUID: ...

    @abstractmethod
    def to_payload(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class PaymentCreated(DomainEvent):
    EVENT_TYPE = "payment.created"

    payment_id: UUID
    amount: str
    currency: str

    @property
    def event_type(self) -> str:
        return self.EVENT_TYPE

    @property
    def aggregate_id(self) -> UUID:
        return self.payment_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "payment_id": str(self.payment_id),
            "amount": self.amount,
            "currency": self.currency,
        }
