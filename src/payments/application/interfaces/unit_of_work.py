from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self

from payments.application.interfaces.repositories import (
    IOutboxRepository,
    IPaymentRepository,
)


class IUnitOfWork(ABC):
    """Транзакция, внутри которой работают репозитории"""

    @property
    @abstractmethod
    def payments(self) -> IPaymentRepository: ...

    @property
    @abstractmethod
    def outbox(self) -> IOutboxRepository: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...

    @abstractmethod
    async def __aenter__(self) -> Self: ...

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class IUnitOfWorkFactory(ABC):
    @abstractmethod
    def create(self) -> IUnitOfWork: ...
