from abc import ABC, abstractmethod
from uuid import UUID

from payments.application.dto import CreatePaymentCommand, PaymentView


class ICreatePaymentUseCase(ABC):
    @abstractmethod
    async def execute(self, command: CreatePaymentCommand) -> PaymentView: ...


class IGetPaymentUseCase(ABC):
    @abstractmethod
    async def execute(self, payment_id: UUID) -> PaymentView: ...


class IProcessPaymentUseCase(ABC):
    @abstractmethod
    async def execute(self, payment_id: UUID) -> None: ...


class IPublishOutboxEventsUseCase(ABC):
    @abstractmethod
    async def execute(self) -> int: ...
