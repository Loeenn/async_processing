import logging
from uuid import UUID

from payments.application.dto import WebhookNotification
from payments.application.interfaces.ports import (
    GatewayResult,
    IClock,
    IPaymentGateway,
    IWebhookSender,
)
from payments.application.interfaces.unit_of_work import IUnitOfWorkFactory
from payments.application.interfaces.use_cases import IProcessPaymentUseCase
from payments.domain.payment import Payment


class ProcessPaymentUseCase(IProcessPaymentUseCase):
    """Проводит платёж через шлюз и уведомляет клиента о результате"""

    def __init__(
        self,
        uow_factory: IUnitOfWorkFactory,
        gateway: IPaymentGateway,
        webhook_sender: IWebhookSender,
        clock: IClock,
        logger: logging.Logger,
    ) -> None:
        self._uow_factory = uow_factory
        self._gateway = gateway
        self._webhook_sender = webhook_sender
        self._clock = clock
        self._logger = logger

    async def execute(self, payment_id: UUID) -> None:
        payment = await self._load(payment_id)
        if payment is None:
            self._logger.warning("payment %s not found, message skipped", payment_id)
            return

        # Повторная доставка сообщения не должна проводить платёж заново
        if not payment.is_processed:
            payment = await self._process(payment)
            self._logger.info(
                "payment %s processed with status %s", payment_id, payment.status
            )
        else:
            self._logger.info(
                "payment %s already processed, resending webhook", payment_id
            )

        await self._webhook_sender.send(self._build_notification(payment))

    async def _process(self, payment: Payment) -> Payment:
        # Поход во внешний шлюз держим вне транзакции, чтобы не занимать
        # соединение с БД на все 2-5 секунд обработки
        result = await self._gateway.process(payment.money)
        processed_at = self._clock.now()

        if result is GatewayResult.SUCCESS:
            payment.mark_succeeded(processed_at)
        else:
            payment.mark_failed(processed_at)

        async with self._uow_factory.create() as uow:
            saved = await uow.payments.save_processing_result(payment)
            await uow.commit()

        if saved:
            return payment

        # Платёж успел обработать другой consumer - работаем с его результатом
        self._logger.info("payment %s was processed concurrently", payment.payment_id)
        actual = await self._load(payment.payment_id)
        return actual or payment

    async def _load(self, payment_id: UUID) -> Payment | None:
        async with self._uow_factory.create() as uow:
            return await uow.payments.get(payment_id)

    @staticmethod
    def _build_notification(payment: Payment) -> WebhookNotification:
        return WebhookNotification(
            url=payment.webhook_url,
            payload={
                "payment_id": str(payment.payment_id),
                "status": payment.status,
                "amount": str(payment.money.amount),
                "currency": payment.money.currency,
                "description": payment.description,
                "metadata": payment.metadata,
                "processed_at": (
                    payment.processed_at.isoformat() if payment.processed_at else None
                ),
            },
        )
