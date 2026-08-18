from collections.abc import Mapping

from payments.application.dto import OutboxMessage
from payments.application.interfaces.ports import IIdGenerator
from payments.domain.events import DomainEvent
from payments.domain.payment import Payment, PaymentStatus
from payments.domain.value_objects import Currency, Money
from payments.infrastructure.database.models import OutboxModel, PaymentModel


class PaymentMapper:
    @staticmethod
    def to_model(payment: Payment) -> PaymentModel:
        return PaymentModel(
            payment_id=payment.payment_id,
            amount=payment.money.amount,
            currency=payment.money.currency,
            description=payment.description,
            payment_metadata=payment.metadata,
            status=payment.status,
            idempotency_key=payment.idempotency_key,
            webhook_url=payment.webhook_url,
            created_at=payment.created_at,
            processed_at=payment.processed_at,
        )

    @staticmethod
    def to_entity(model: PaymentModel) -> Payment:
        return Payment(
            payment_id=model.payment_id,
            money=Money(amount=model.amount, currency=Currency(model.currency)),
            description=model.description,
            metadata=model.payment_metadata,
            idempotency_key=model.idempotency_key,
            webhook_url=model.webhook_url,
            status=PaymentStatus(model.status),
            created_at=model.created_at,
            processed_at=model.processed_at,
        )


class OutboxMapper:
    """Превращает доменные события в строки outbox

    соответствие "тип события - routing key" задаётся при сборке приложения,
    поэтому новый тип события не требует правок в репозитории
    """

    def __init__(
        self, id_generator: IIdGenerator, routing_keys: Mapping[str, str]
    ) -> None:
        self._id_generator = id_generator
        self._routing_keys = routing_keys

    def to_model(self, event: DomainEvent) -> OutboxModel:
        routing_key = self._routing_keys.get(event.event_type)
        if routing_key is None:
            message = f"routing key is not configured for event {event.event_type}"
            raise ValueError(message)

        return OutboxModel(
            event_id=self._id_generator.generate(),
            aggregate_id=event.aggregate_id,
            event_type=event.event_type,
            routing_key=routing_key,
            payload=event.to_payload(),
            occurred_at=event.occurred_at,
        )

    @staticmethod
    def to_message(model: OutboxModel) -> OutboxMessage:
        return OutboxMessage(
            event_id=model.event_id,
            routing_key=model.routing_key,
            payload=model.payload,
        )
