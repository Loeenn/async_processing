import asyncio
import random

from bootstrap.config import GatewayConfig
from payments.application.interfaces.ports import GatewayResult, IPaymentGateway
from payments.domain.value_objects import Money


class EmulatedPaymentGateway(IPaymentGateway):
    """Эмуляция внешнего шлюза: обработка занимает 2-5 секунд и иногда падает"""

    def __init__(self, config: GatewayConfig) -> None:
        self._config = config

    async def process(self, money: Money) -> GatewayResult:
        delay = random.uniform(self._config.min_delay, self._config.max_delay)
        await asyncio.sleep(delay)

        if random.random() < self._config.success_rate:
            return GatewayResult.SUCCESS
        return GatewayResult.FAILURE
