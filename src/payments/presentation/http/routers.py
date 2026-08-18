from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status

from payments.application.dto import CreatePaymentCommand
from payments.application.exceptions import PaymentNotFoundError
from payments.application.interfaces.use_cases import (
    ICreatePaymentUseCase,
    IGetPaymentUseCase,
)
from payments.domain.exceptions import InvariantViolationError
from payments.presentation.http.dto import (
    CreatePaymentRequest,
    CreatePaymentResponse,
    PaymentResponse,
)


def build_payments_router(
    create_payment: ICreatePaymentUseCase,
    get_payment: IGetPaymentUseCase,
) -> APIRouter:
    router = APIRouter()

    @router.post("", status_code=status.HTTP_202_ACCEPTED)
    async def create(
        request: CreatePaymentRequest,
        idempotency_key: Annotated[
            str, Header(alias="Idempotency-Key", max_length=255)
        ],
    ) -> CreatePaymentResponse:
        command = CreatePaymentCommand(
            idempotency_key=idempotency_key,
            amount=request.amount,
            currency=request.currency,
            description=request.description,
            metadata=request.metadata,
            webhook_url=str(request.webhook_url),
        )
        try:
            payment = await create_payment.execute(command)
        except InvariantViolationError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
            ) from error

        return CreatePaymentResponse.from_view(payment)

    @router.get("/{payment_id}")
    async def get(payment_id: UUID) -> PaymentResponse:
        try:
            payment = await get_payment.execute(payment_id)
        except PaymentNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error),
            ) from error

        return PaymentResponse.from_view(payment)

    return router


def build_health_router() -> APIRouter:
    """Отдельный роутер без авторизации - для проб Docker и оркестратора"""
    router = APIRouter()

    @router.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return router
