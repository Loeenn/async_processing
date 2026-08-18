import asyncio
import logging

import httpx

from bootstrap.config import WebhookConfig
from payments.application.dto import WebhookNotification
from payments.application.exceptions import WebhookDeliveryError
from payments.application.interfaces.ports import IWebhookSender


class HttpWebhookSender(IWebhookSender):
    def __init__(
        self,
        client: httpx.AsyncClient,
        config: WebhookConfig,
        logger: logging.Logger,
    ) -> None:
        self._client = client
        self._config = config
        self._logger = logger

    async def send(self, notification: WebhookNotification) -> None:
        """Отправляет уведомление, повторяя попытки с экспоненциальной задержкой"""
        delay = self._config.initial_delay

        for attempt in range(1, self._config.max_attempts + 1):
            try:
                response = await self._client.post(
                    notification.url, json=notification.payload
                )
                response.raise_for_status()
            except httpx.HTTPError as error:
                self._logger.warning(
                    "webhook attempt %s/%s to %s failed: %s",
                    attempt,
                    self._config.max_attempts,
                    notification.url,
                    error,
                )
                if attempt == self._config.max_attempts:
                    message = f"webhook delivery to {notification.url} failed"
                    raise WebhookDeliveryError(message) from error

                await asyncio.sleep(delay)
                delay *= 2
            else:
                self._logger.info("webhook to %s delivered", notification.url)
                return
