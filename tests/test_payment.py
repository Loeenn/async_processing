from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from payments.domain.events import PaymentCreated
from payments.domain.exceptions import InvariantViolationError
from payments.domain.payment import Payment, PaymentStatus
from payments.domain.value_objects import Currency, Money


CREATED_AT = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
PROCESSED_AT = datetime(2026, 8, 18, 12, 0, 5, tzinfo=UTC)


def make_payment() -> Payment:
    return Payment.create(
        payment_id=uuid4(),
        money=Money(amount=Decimal("100.00"), currency=Currency.RUB),
        description="test",
        metadata={"order_id": 1},
        idempotency_key="key",
        webhook_url="https://example.com/hook",
        created_at=CREATED_AT,
    )


def test_new_payment_is_pending_and_registers_event():
    payment = make_payment()

    assert payment.status is PaymentStatus.PENDING
    assert payment.is_processed is False

    events = payment.pull_events()
    assert len(events) == 1
    assert isinstance(events[0], PaymentCreated)
    assert events[0].to_payload()["amount"] == "100.00"
    # Второй вызов уже ничего не отдаёт - события забирают ровно один раз
    assert payment.pull_events() == []


def test_mark_succeeded_sets_status_and_time():
    payment = make_payment()

    payment.mark_succeeded(PROCESSED_AT)

    assert payment.status is PaymentStatus.SUCCEEDED
    assert payment.processed_at == PROCESSED_AT
    assert payment.is_processed is True


def test_payment_cannot_be_processed_twice():
    payment = make_payment()
    payment.mark_failed(PROCESSED_AT)

    with pytest.raises(InvariantViolationError):
        payment.mark_succeeded(PROCESSED_AT)


@pytest.mark.parametrize("amount", ["0", "-10.00", "10.005"])
def test_money_rejects_invalid_amount(amount):
    with pytest.raises(InvariantViolationError):
        Money(amount=Decimal(amount), currency=Currency.USD)
