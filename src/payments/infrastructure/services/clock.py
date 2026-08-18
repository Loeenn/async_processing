from datetime import UTC, datetime

from payments.application.interfaces.ports import IClock


class SystemClock(IClock):
    def now(self) -> datetime:
        return datetime.now(UTC)
