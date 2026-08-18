from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bootstrap.config import DatabaseConfig


def create_engine(config: DatabaseConfig) -> AsyncEngine:
    return create_async_engine(
        config.url,
        echo=config.echo,
        pool_pre_ping=True,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
    )


def create_session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
