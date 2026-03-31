import aio_pika
from aio_pika.abc import AbstractRobustConnection
from core.logger import logger
from core.config import settings

_connection: AbstractRobustConnection | None = None


async def get_connection() -> AbstractRobustConnection:
    """Get or create a robust (auto-reconnecting) RabbitMQ connection."""
    global _connection

    if _connection is None or _connection.is_closed:
        logger.info(f"Connecting to RabbitMQ at {settings.RABBITMQ_URL}...")
        _connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        logger.info("Connected to RabbitMQ successfully.")

    return _connection


async def close_connection() -> None:
    """Gracefully close the RabbitMQ connection."""
    global _connection

    if _connection and not _connection.is_closed:
        await _connection.close()
        logger.info("RabbitMQ connection closed.")
        _connection = None
