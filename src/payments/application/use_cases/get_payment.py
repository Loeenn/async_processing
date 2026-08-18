from uuid import UUID

from payments.application.dto import PaymentView
from payments.application.exceptions import PaymentNotFoundError
from payments.application.interfaces.unit_of_work import IUnitOfWorkFactory
from payments.application.interfaces.use_cases import IGetPaymentUseCase


class GetPaymentUseCase(IGetPaymentUseCase):
    def __init__(self, uow_factory: IUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, payment_id: UUID) -> PaymentView:
        async with self._uow_factory.create() as uow:
            payment = await uow.payments.get(payment_id)

        if payment is None:
            raise PaymentNotFoundError(payment_id)

        return PaymentView.from_entity(payment)
