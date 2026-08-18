from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from payments.application.dto import OutboxMessage, WebhookNotification
from payments.domain.value_objects import Money


class GatewayResult(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class IPaymentGateway(ABC):
    """Внешний платёжный шлюз"""

    @abstractmethod
    async def process(self, money: Money) -> GatewayResult: ...


class IWebhookSender(ABC):
    @abstractmethod
    async def send(self, notification: WebhookNotification) -> None:
        """Доставляет уведомление или бросает WebhookDeliveryError"""


class IEventPublisher(ABC):
    @abstractmethod
    async def publish(self, message: OutboxMessage) -> None: ...


class IClock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...


class IIdGenerator(ABC):
    @abstractmethod
    def generate(self) -> UUID: ...
