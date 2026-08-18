from decimal import Decimal

from payments.application.dto import CreatePaymentCommand
from payments.application.use_cases.create_payment import CreatePaymentUseCase
from payments.domain.payment import PaymentStatus
from payments.domain.value_objects import Currency
from tests.fakes import (
    FakeClock,
    FakeIdGenerator,
    FakeUnitOfWorkFactory,
    Storage,
    make_payment,
)


def make_command(idempotency_key: str = "order-1") -> CreatePaymentCommand:
    return CreatePaymentCommand(
        idempotency_key=idempotency_key,
        amount=Decimal("1500.00"),
        currency=Currency.RUB,
        description="Оплата заказа",
        metadata={"order_id": 1},
        webhook_url="https://example.com/hook",
    )


def make_use_case(storage: Storage) -> CreatePaymentUseCase:
    return CreatePaymentUseCase(
        FakeUnitOfWorkFactory(storage), FakeClock(), FakeIdGenerator()
    )


async def test_creates_pending_payment_with_outbox_event():
    storage = Storage()

    view = await make_use_case(storage).execute(make_command())

    assert view.status == PaymentStatus.PENDING
    assert storage.payments[view.payment_id].idempotency_key == "order-1"
    # Событие лежит в outbox, в брокер use case не ходит
    assert len(storage.outbox) == 1
    assert storage.outbox[0].payload["payment_id"] == str(view.payment_id)


async def test_same_idempotency_key_returns_existing_payment():
    storage = Storage()
    use_case = make_use_case(storage)

    first = await use_case.execute(make_command())
    second = await use_case.execute(make_command())

    assert first.payment_id == second.payment_id
    assert len(storage.payments) == 1
    # Повторный запрос не должен порождать второе событие
    assert len(storage.outbox) == 1


async def test_concurrent_request_falls_back_to_stored_payment():
    """Дубль поймал уникальный индекс - отдаём платёж, созданный конкурентом"""
    storage = Storage()
    competitor = make_payment(idempotency_key="order-1")
    # Конкурент коммитится между нашим SELECT и INSERT
    storage.duplicate_on_commit = True
    storage.competitor = competitor

    view = await make_use_case(storage).execute(make_command("order-1"))

    assert view.payment_id == competitor.payment_id
