import logging

import httpx
import pytest

from bootstrap.config import WebhookConfig
from payments.application.dto import WebhookNotification
from payments.application.exceptions import WebhookDeliveryError
from payments.infrastructure.webhooks.http_sender import HttpWebhookSender


NOTIFICATION = WebhookNotification(url="https://example.com/hook", payload={"a": 1})


@pytest.fixture
def delays(monkeypatch):
    """Убирает реальные паузы между попытками и запоминает их длительность"""
    recorded: list[float] = []

    async def fake_sleep(delay: float) -> None:
        recorded.append(delay)

    monkeypatch.setattr(
        "payments.infrastructure.webhooks.http_sender.asyncio.sleep", fake_sleep
    )
    return recorded


def make_sender(statuses: list[int]) -> HttpWebhookSender:
    responses = iter(statuses)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(next(responses))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    config = WebhookConfig(max_attempts=3, initial_delay=1.0)
    return HttpWebhookSender(client, config, logging.getLogger("test"))


async def test_successful_delivery_does_not_retry(delays):
    await make_sender([200]).send(NOTIFICATION)

    assert delays == []


async def test_retries_until_success(delays):
    await make_sender([500, 502, 200]).send(NOTIFICATION)

    # Задержки растут экспоненциально
    assert delays == [1.0, 2.0]


async def test_raises_after_three_failed_attempts(delays):
    with pytest.raises(WebhookDeliveryError):
        await make_sender([500, 500, 500]).send(NOTIFICATION)

    assert delays == [1.0, 2.0]
