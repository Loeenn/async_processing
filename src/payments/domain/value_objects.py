from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from payments.domain.exceptions import InvariantViolationError


class Currency(StrEnum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


@dataclass(frozen=True)
class Money:
    """Сумма платежа вместе с валютой

    держим их вместе, чтобы нельзя было случайно сложить рубли с евро или
    создать платёж на отрицательную сумму
    """

    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        if self.amount <= 0:
            message = f"amount must be positive, got {self.amount}"
            raise InvariantViolationError(message)

        exponent = self.amount.as_tuple().exponent
        # Если exponent не int или меньше -2, то amount имеет более 2 десятичных знаков
        if not isinstance(exponent, int) or exponent < -2:
            message = f"amount must have at most 2 decimal places, got {self.amount}"
            raise InvariantViolationError(message)
