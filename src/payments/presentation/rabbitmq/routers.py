from faststream import AckPolicy
from faststream.rabbit import Channel, RabbitRouter

from payments.application.interfaces.use_cases import IProcessPaymentUseCase
from payments.infrastructure.messaging.topology import (
    NEW_PAYMENTS_QUEUE,
    PAYMENTS_EXCHANGE,
)
from payments.presentation.rabbitmq.dto import PaymentCreatedMessage


def build_payments_router(
    process_payment: IProcessPaymentUseCase,
    prefetch_count: int,
) -> RabbitRouter:
    router = RabbitRouter()

    @router.subscriber(
        NEW_PAYMENTS_QUEUE,
        exchange=PAYMENTS_EXCHANGE,
        # prefetch ограничивает число платежей в работе, чтобы consumer не
        # выгребал весь пул соединений к БД
        channel=Channel(prefetch_count=prefetch_count),
        # Ошибка в обработчике = reject без requeue, то есть сообщение уедет в DLQ
        ack_policy=AckPolicy.REJECT_ON_ERROR,
    )
    async def process(message: PaymentCreatedMessage) -> None:
        await process_payment.execute(message.payment_id)

    return router
