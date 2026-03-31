import os
import sys
import asyncio
import signal

# Fix import path when running from project root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.logger import logger
from core.health import start_health_server, stop_health_server
from mq.connection import get_connection, close_connection
from mq.consumer import WritingConsumer
from services.evaluation_llm import close_http_client


async def main() -> None:
    logger.info("Starting AI Microservice (RabbitMQ Worker)...")

    # Start health check server
    health_runner = await start_health_server()

    # Connect to RabbitMQ and start consuming
    connection = await get_connection()
    consumer = WritingConsumer(connection)
    await consumer.start()

    logger.info("AI Worker is running. Waiting for messages... (Ctrl+C to stop)")

    # Keep the event loop alive until interrupted
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received.")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows does not support add_signal_handler
            pass

    try:
        await stop_event.wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        logger.info("Shutting down worker...")
        await stop_health_server(health_runner)
        await close_http_client()
        await close_connection()
        logger.info("Worker stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass