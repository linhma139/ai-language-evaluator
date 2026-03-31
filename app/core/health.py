import json
from aiohttp import web
from core.logger import logger
from core.config import settings
from mq.connection import get_connection


async def health_handler(request: web.Request) -> web.Response:
    """Health check endpoint for monitoring and orchestration (K8s, Docker, etc.)."""
    try:
        connection = await get_connection()
        rabbitmq_ok = connection and not connection.is_closed
    except Exception:
        rabbitmq_ok = False

    status_code = 200 if rabbitmq_ok else 503
    body = {
        "status": "healthy" if rabbitmq_ok else "unhealthy",
        "rabbitmq": "connected" if rabbitmq_ok else "disconnected",
    }

    return web.json_response(body, status=status_code)


async def start_health_server() -> web.AppRunner:
    """Start a lightweight HTTP health check server."""
    app = web.Application()
    app.router.add_get("/health", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", settings.HEALTH_CHECK_PORT)
    await site.start()

    logger.info(f"Health check server running on http://0.0.0.0:{settings.HEALTH_CHECK_PORT}/health")
    return runner


async def stop_health_server(runner: web.AppRunner) -> None:
    """Stop the health check server."""
    if runner:
        await runner.cleanup()
        logger.info("Health check server stopped.")
