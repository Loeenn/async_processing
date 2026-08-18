from types import TracebackType
from typing import Self

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from payments.application.exceptions import DuplicateIdempotencyKeyError
from payments.application.interfaces.repositories import (
    IOutboxRepository,
    IPaymentRepository,
)
from payments.application.interfaces.unit_of_work import IUnitOfWork, IUnitOfWorkFactory
from payments.infrastructure.database.mappers import OutboxMapper, PaymentMapper
from payments.infrastructure.database.models import UNIQUE_IDEMPOTENCY_KEY_CONSTRAINT
from payments.infrastructure.database.repositories import (
    OutboxRepository,
    PaymentRepository,
)


class SqlAlchemyUnitOfWork(IUnitOfWork):
    _NOT_STARTED = "unit of work is used outside of `async with`"

    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        payment_mapper: PaymentMapper,
        outbox_mapper: OutboxMapper,
    ) -> None:
        self._session_maker = session_maker
        self._payment_mapper = payment_mapper
        self._outbox_mapper = outbox_mapper
        self._session: AsyncSession | None = None
        self._payments: IPaymentRepository | None = None
        self._outbox: IOutboxRepository | None = None

    @property
    def payments(self) -> IPaymentRepository:
        if self._payments is None:
            raise RuntimeError(self._NOT_STARTED)
        return self._payments

    @property
    def outbox(self) -> IOutboxRepository:
        if self._outbox is None:
            raise RuntimeError(self._NOT_STARTED)
        return self._outbox

    async def commit(self) -> None:
        session = self._require_session()
        try:
            await session.commit()
        except IntegrityError as error:
            await session.rollback()
            if UNIQUE_IDEMPOTENCY_KEY_CONSTRAINT in str(error.orig):
                raise DuplicateIdempotencyKeyError from error
            raise

    async def rollback(self) -> None:
        await self._require_session().rollback()

    async def __aenter__(self) -> Self:
        session = self._session_maker()
        self._session = session
        self._payments = PaymentRepository(session, self._payment_mapper)
        self._outbox = OutboxRepository(session, self._outbox_mapper)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._require_session()
        try:
            # Всё, что не закоммитили явно, откатываем
            await session.rollback()
        finally:
            await session.close()
            self._session = None
            self._payments = None
            self._outbox = None

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError(self._NOT_STARTED)
        return self._session


class SqlAlchemyUnitOfWorkFactory(IUnitOfWorkFactory):
    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        payment_mapper: PaymentMapper,
        outbox_mapper: OutboxMapper,
    ) -> None:
        self._session_maker = session_maker
        self._payment_mapper = payment_mapper
        self._outbox_mapper = outbox_mapper

    def create(self) -> IUnitOfWork:
        return SqlAlchemyUnitOfWork(
            self._session_maker, self._payment_mapper, self._outbox_mapper
        )
