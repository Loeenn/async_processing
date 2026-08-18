from payments.application.interfaces.ports import IClock, IEventPublisher
from payments.application.interfaces.unit_of_work import IUnitOfWorkFactory
from payments.application.interfaces.use_cases import IPublishOutboxEventsUseCase


class PublishOutboxEventsUseCase(IPublishOutboxEventsUseCase):
    """Перекладывает события из таблицы outbox в брокер"""

    def __init__(
        self,
        uow_factory: IUnitOfWorkFactory,
        publisher: IEventPublisher,
        clock: IClock,
        batch_size: int,
    ) -> None:
        self._uow_factory = uow_factory
        self._publisher = publisher
        self._clock = clock
        self._batch_size = batch_size

    async def execute(self) -> int:
        async with self._uow_factory.create() as uow:
            messages = await uow.outbox.fetch_unpublished(self._batch_size)
            if not messages:
                return 0

            for message in messages:
                await self._publisher.publish(message)

            await uow.outbox.mark_published(
                [message.event_id for message in messages], self._clock.now()
            )
            await uow.commit()

        return len(messages)
