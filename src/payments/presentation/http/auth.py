import secrets
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader


api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=True, scheme_name="API Key")


def build_api_key_guard(expected_key: str) -> Callable[..., Awaitable[None]]:
    """Возвращает зависимость, которая пускает дальше только с верным ключом"""

    async def verify_api_key(
        api_key: Annotated[str, Security(api_key_scheme)],
    ) -> None:
        # compare_digest вместо ==, чтобы ключ нельзя было подобрать по времени ответа
        if not secrets.compare_digest(api_key, expected_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )

    return verify_api_key
