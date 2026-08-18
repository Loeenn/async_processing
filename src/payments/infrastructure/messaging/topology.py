from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from payments.domain.events import PaymentCreated


PAYMENT_CREATED_ROUTING_KEY = "payments.new"

# Соответствие доменного события и routing key: новый тип события добавляется
# только сюда, остальной код про него знать не обязан
ROUTING_KEYS = {PaymentCreated.EVENT_TYPE: PAYMENT_CREATED_ROUTING_KEY}

PAYMENTS_EXCHANGE = RabbitExchange("payments", type=ExchangeType.TOPIC, durable=True)
# Обменник, в который RabbitMQ сам перекладывает отклонённые сообщения
PAYMENTS_DLX = RabbitExchange("payments.dlx", type=ExchangeType.TOPIC, durable=True)

NEW_PAYMENTS_QUEUE = RabbitQueue(
    "payments.new",
    durable=True,
    routing_key=PAYMENT_CREATED_ROUTING_KEY,
    arguments={"x-dead-letter-exchange": PAYMENTS_DLX.name},
)
NEW_PAYMENTS_DLQ = RabbitQueue(
    "payments.new.dlq",
    durable=True,
    routing_key=PAYMENT_CREATED_ROUTING_KEY,
)


async def declare_topology(broker: RabbitBroker) -> None:
    """Объявляет обменники, очереди и их связки

    каждый сервис делает это у себя на старте, поэтому порядок запуска
    контейнеров не имеет значения
    """
    pairs = (
        (PAYMENTS_EXCHANGE, NEW_PAYMENTS_QUEUE),
        (PAYMENTS_DLX, NEW_PAYMENTS_DLQ),
    )
    for exchange, queue in pairs:
        declared_exchange = await broker.declare_exchange(exchange)
        declared_queue = await broker.declare_queue(queue)
        await declared_queue.bind(declared_exchange, routing_key=queue.routing_key)
