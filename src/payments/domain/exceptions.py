class DomainError(Exception):
    """Базовая ошибка доменного слоя"""


class InvariantViolationError(DomainError):
    """Операция нарушает инвариант домена"""
