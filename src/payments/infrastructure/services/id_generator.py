from uuid import UUID, uuid4

from payments.application.interfaces.ports import IIdGenerator


class UuidGenerator(IIdGenerator):
    def generate(self) -> UUID:
        return uuid4()
