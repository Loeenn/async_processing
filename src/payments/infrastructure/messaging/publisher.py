from faststream.rabbit import RabbitBroker, RabbitExchange

from payments.application.dto import OutboxMessage
from payments.application.interfaces.ports import IEventPublisher


class RabbitEventPublisher(IEventPublisher):
    def __init__(self, broker: RabbitBroker, exchange: RabbitExchange) -> None:
        self._broker = broker
        self._exchange = exchange

    async def publish(self, message: OutboxMessage) -> None:
        await self._broker.publish(
            message.payload,
            exchange=self._exchange,
            routing_key=message.routing_key,
            # message_id = id строки в outbox: по нему получатель может
            # отбросить дубль при повторной публикации
            message_id=str(message.event_id),
            persist=True,
        )
