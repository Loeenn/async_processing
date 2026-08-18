class ApplicationError(Exception):
    """Базовая ошибка прикладного слоя"""


class PaymentNotFoundError(ApplicationError):
    def __init__(self, payment_id: object) -> None:
        super().__init__(f"payment {payment_id} not found")


class DuplicateIdempotencyKeyError(ApplicationError):
    def __init__(self, idempotency_key: str | None = None) -> None:
        target = f" {idempotency_key}" if idempotency_key else ""
        super().__init__(f"payment with idempotency key{target} already exists")


class WebhookDeliveryError(ApplicationError):
    """Уведомление не доставлено за отведённое число попыток"""
