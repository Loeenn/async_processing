from uuid import uuid4

from payments.application.use_cases.publish_outbox_events import (
    PublishOutboxEventsUseCase,
)
from tests.fakes import (
    FakeClock,
    FakePublisher,
    FakeUnitOfWorkFactory,
    OutboxRecord,
    Storage,
)


def make_use_case(
    storage: Storage, publisher: FakePublisher
) -> PublishOutboxEventsUseCase:
    return PublishOutboxEventsUseCase(
        uow_factory=FakeUnitOfWorkFactory(storage),
        publisher=publisher,
        clock=FakeClock(),
        batch_size=10,
    )


async def test_publishes_events_and_marks_them_published():
    storage = Storage()
    storage.outbox.append(
        OutboxRecord(event_id=uuid4(), routing_key="payments.new", payload={"a": 1})
    )
    publisher = FakePublisher()

    published = await make_use_case(storage, publisher).execute()

    assert published == 1
    assert publisher.published[0].payload == {"a": 1}
    assert storage.outbox[0].published_at is not None


async def test_second_run_does_not_republish():
    storage = Storage()
    storage.outbox.append(
        OutboxRecord(event_id=uuid4(), routing_key="payments.new", payload={})
    )
    publisher = FakePublisher()
    use_case = make_use_case(storage, publisher)

    await use_case.execute()
    published = await use_case.execute()

    assert published == 0
    assert len(publisher.published) == 1
