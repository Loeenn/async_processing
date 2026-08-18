from typing import Self
from urllib.parse import quote

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseModel):
    host: str
    port: int = 5432
    user: str
    password: str
    name: str
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10

    @property
    def url(self) -> str:
        user = quote(self.user, safe="")
        password = quote(self.password, safe="")
        name = quote(self.name, safe="")
        return f"postgresql+asyncpg://{user}:{password}@{self.host}:{self.port}/{name}"


class RabbitConfig(BaseModel):
    host: str
    port: int = 5672
    user: str
    password: str
    vhost: str = "/"

    @property
    def url(self) -> str:
        user = quote(self.user, safe="")
        password = quote(self.password, safe="")
        vhost = quote(self.vhost, safe="")
        return f"amqp://{user}:{password}@{self.host}:{self.port}/{vhost}"


class GatewayConfig(BaseModel):
    """Параметры эмуляции внешнего платёжного шлюза"""

    min_delay: float = 2.0
    max_delay: float = 5.0
    success_rate: float = 0.9


class WebhookConfig(BaseModel):
    timeout: float = 5.0
    max_attempts: int = 3
    # Задержки между попытками: initial_delay, initial_delay * 2, initial_delay * 4 ...
    initial_delay: float = 1.0


class OutboxConfig(BaseModel):
    batch_size: int = 100
    poll_interval: float = 1.0


class ConsumerConfig(BaseModel):
    prefetch_count: int = 10


class AppConfig(BaseSettings):
    api_key: str
    log_level: str = "INFO"
    db: DatabaseConfig
    rabbit: RabbitConfig
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    webhook: WebhookConfig = Field(default_factory=WebhookConfig)
    outbox: OutboxConfig = Field(default_factory=OutboxConfig)
    consumer: ConsumerConfig = Field(default_factory=ConsumerConfig)

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def load(cls) -> Self:
        return cls()
