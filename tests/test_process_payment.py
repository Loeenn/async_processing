import logging
from uuid import uuid4

import pytest

from payments.application.exceptions import WebhookDeliveryError
from payments.application.interfaces.ports import GatewayResult
from payments.application.use_cases.process_payment import ProcessPaymentUseCase
from payments.domain.payment import PaymentStatus
from tests.fakes import (
    FakeClock,
    FakeGateway,
    FakeUnitOfWorkFactory,
    FakeWebhookSender,
    Storage,
    make_payment,
)


def make_use_case(
    storage: Storage,
    gateway: FakeGateway,
    sender: FakeWebhookSender,
) -> ProcessPaymentUseCase:
    return ProcessPaymentUseCase(
        uow_factory=FakeUnitOfWorkFactory(storage),
        gateway=gateway,
        webhook_sender=sender,
        clock=FakeClock(),
        logger=logging.getLogger("test"),
    )


@pytest.mark.parametrize(
    ("result", "expected_status"),
    [
        (GatewayResult.SUCCESS, PaymentStatus.SUCCEEDED),
        (GatewayResult.FAILURE, PaymentStatus.FAILED),
    ],
)
async def test_payment_gets_final_status_and_webhook(result, expected_status):
    storage = Storage()
    payment = make_payment()
    storage.payments[payment.payment_id] = payment
    sender = FakeWebhookSender()

    await make_use_case(storage, FakeGateway(result), sender).execute(
        payment.payment_id
    )

    assert storage.payments[payment.payment_id].status is expected_status
    assert len(sender.sent) == 1
    assert sender.sent[0].payload["status"] == expected_status


async def test_already_processed_payment_only_gets_webhook():
    """Повторная доставка сообщения не должна проводить платёж заново"""
    storage = Storage()
    payment = make_payment(status=PaymentStatus.SUCCEEDED)
    storage.payments[payment.payment_id] = payment
    gateway = FakeGateway(GatewayResult.SUCCESS)
    sender = FakeWebhookSender()

    await make_use_case(storage, gateway, sender).execute(payment.payment_id)

    assert gateway.calls == 0
    assert len(sender.sent) == 1


async def test_unknown_payment_is_skipped():
    storage = Storage()
    gateway = FakeGateway(GatewayResult.SUCCESS)
    sender = FakeWebhookSender()

    await make_use_case(storage, gateway, sender).execute(uuid4())

    assert gateway.calls == 0
    assert sender.sent == []


async def test_webhook_failure_propagates_for_dlq():
    """Ошибка доставки должна дойти до брокера, иначе сообщение не попадёт в DLQ"""
    storage = Storage()
    payment = make_payment()
    storage.payments[payment.payment_id] = payment
    sender = FakeWebhookSender(error=WebhookDeliveryError("no luck"))

    use_case = make_use_case(storage, FakeGateway(GatewayResult.SUCCESS), sender)

    with pytest.raises(WebhookDeliveryError):
        await use_case.execute(payment.payment_id)

    # Статус при этом уже сохранён - повторная обработка его не тронет
    assert storage.payments[payment.payment_id].status is PaymentStatus.SUCCEEDED
