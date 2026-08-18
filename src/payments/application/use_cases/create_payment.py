from payments.application.dto import CreatePaymentCommand, PaymentView
from payments.application.exceptions import DuplicateIdempotencyKeyError
from payments.application.interfaces.ports import IClock, IIdGenerator
from payments.application.interfaces.unit_of_work import IUnitOfWorkFactory
from payments.application.interfaces.use_cases import ICreatePaymentUseCase
from payments.domain.payment import Payment
from payments.domain.value_objects import Money


class CreatePaymentUseCase(ICreatePaymentUseCase):
    """Создаёт платёж и событие для брокера в одной транзакции (outbox)"""

    def __init__(
        self,
        uow_factory: IUnitOfWorkFactory,
        clock: IClock,
        id_generator: IIdGenerator,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._id_generator = id_generator

    async def execute(self, command: CreatePaymentCommand) -> PaymentView:
        existing = await self._find_by_key(command.idempotency_key)
        if existing is not None:
            return existing

        try:
            return await self._create(command)
        except DuplicateIdempotencyKeyError:
            # Одинаковые запросы пришли одновременно: уникальный индекс не дал
            # создать дубль, отдаём тот платёж, который уже лежит в БД
            duplicate = await self._find_by_key(command.idempotency_key)
            if duplicate is None:
                raise
            return duplicate

    async def _create(self, command: CreatePaymentCommand) -> PaymentView:
        payment = Payment.create(
            payment_id=self._id_generator.generate(),
            money=Money(amount=command.amount, currency=command.currency),
            description=command.description,
            metadata=command.metadata,
            idempotency_key=command.idempotency_key,
            webhook_url=command.webhook_url,
            created_at=self._clock.now(),
        )

        async with self._uow_factory.create() as uow:
            await uow.payments.add(payment)
            await uow.outbox.add(payment.pull_events())
            await uow.commit()

        return PaymentView.from_entity(payment)

    async def _find_by_key(self, idempotency_key: str) -> PaymentView | None:
        async with self._uow_factory.create() as uow:
            payment = await uow.payments.find_by_idempotency_key(idempotency_key)

        return PaymentView.from_entity(payment) if payment else None
