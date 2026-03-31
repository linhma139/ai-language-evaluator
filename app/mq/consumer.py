import json
import aio_pika
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection

from core.logger import logger
from core.config import settings
from schemas.writing import WritingRequest, WritingFeedback, WritingResultEvent
from services.evaluation_llm import evaluate_writing_with_local_llm


# Structured error codes for BE to classify errors
class ErrorCode:
    VALIDATION_ERROR = "VALIDATION_ERROR"       # Bad request payload
    LLM_TIMEOUT = "LLM_TIMEOUT"                 # Ollama timed out
    LLM_CONNECTION_ERROR = "LLM_CONNECTION_ERROR"  # Cannot reach Ollama
    LLM_PARSE_ERROR = "LLM_PARSE_ERROR"          # LLM returned unparseable response
    INTERNAL_ERROR = "INTERNAL_ERROR"             # Unexpected server error


class WritingConsumer:
    """
    Consumes messages from the writing evaluation queue,
    processes them through the LLM, and publishes results back
    using the RPC-over-RabbitMQ pattern (reply_to + correlation_id).

    Features:
    - Dead Letter Queue (DLQ) for failed messages after max retries
    - Persistent messages for durability
    - Structured error codes for BE classification
    """

    def __init__(self, connection: AbstractRobustConnection):
        self._connection = connection
        self._channel = None
        self._exchange = None

    async def start(self) -> None:
        """Declare exchange, queues (main + DLQ), bind, set QoS, and consume."""
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=settings.MQ_PREFETCH_COUNT)

        # Declare exchange
        self._exchange = await self._channel.declare_exchange(
            settings.MQ_EXCHANGE_NAME,
            type=aio_pika.ExchangeType[settings.MQ_EXCHANGE_TYPE.upper()],
            durable=True,
        )

        # Declare DLQ first (must exist before main queue references it)
        dlq = await self._channel.declare_queue(
            settings.WRITING_DLQ_NAME,
            durable=True,
        )
        await dlq.bind(self._exchange, routing_key=settings.WRITING_DLQ_ROUTING_KEY)

        # Declare main queue with DLQ and TTL settings
        queue = await self._channel.declare_queue(
            settings.WRITING_QUEUE_NAME,
            durable=True,
            arguments={
                "x-dead-letter-exchange": settings.MQ_EXCHANGE_NAME,
                "x-dead-letter-routing-key": settings.WRITING_DLQ_ROUTING_KEY,
                "x-message-ttl": settings.MQ_MESSAGE_TTL,
            },
        )
        await queue.bind(self._exchange, routing_key=settings.WRITING_ROUTING_KEY)

        await queue.consume(self._on_message)
        logger.info(
            f"Exchange: '{settings.MQ_EXCHANGE_NAME}' ({settings.MQ_EXCHANGE_TYPE}) | "
            f"Queue: '{settings.WRITING_QUEUE_NAME}' | "
            f"DLQ: '{settings.WRITING_DLQ_NAME}' | "
            f"Routing key: '{settings.WRITING_ROUTING_KEY}' | "
            f"Prefetch: {settings.MQ_PREFETCH_COUNT} | "
            f"Max retries: {settings.MQ_MAX_RETRIES} | "
            f"TTL: {settings.MQ_MESSAGE_TTL}ms"
        )

    def _get_retry_count(self, message: AbstractIncomingMessage) -> int:
        """Extract retry count from message headers."""
        headers = message.headers or {}
        return int(headers.get("x-retry-count", 0))

    async def _send_to_dlq(
        self, message: AbstractIncomingMessage, error: str
    ) -> None:
        """Manually publish failed message to DLQ with error context."""
        headers = dict(message.headers or {})
        headers["x-original-routing-key"] = settings.WRITING_ROUTING_KEY
        headers["x-error-reason"] = str(error)[:500]

        await self._exchange.publish(
            aio_pika.Message(
                body=message.body,
                headers=headers,
                correlation_id=message.correlation_id,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=settings.WRITING_DLQ_ROUTING_KEY,
        )
        logger.warning(
            f"Message sent to DLQ '{settings.WRITING_DLQ_NAME}' "
            f"[correlation_id={message.correlation_id}] "
            f"[reason={error}]"
        )

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        """Process a single evaluation request with retry + DLQ support."""
        async with message.process():
            correlation_id = message.correlation_id
            retry_count = self._get_retry_count(message)

            attempt_id = "unknown"
            response_id = "unknown"

            logger.info(
                f"Received message [correlation_id={correlation_id}] [retry={retry_count}/{settings.MQ_MAX_RETRIES}]"
            )

            try:
                # 1. Deserialize and validate request
                try:
                    body = json.loads(message.body.decode())
                    request = WritingRequest(**body)
                    attempt_id = request.attempt_id
                    response_id = request.response_id
                except (json.JSONDecodeError, ValueError) as e:
                    error_msg = f"Invalid payload: {str(e)}"
                    logger.error(f"{error_msg} [correlation_id={correlation_id}]")
                    
                    event = WritingResultEvent(
                        status="error",
                        attempt_id=attempt_id,
                        response_id=response_id,
                        error_code=ErrorCode.VALIDATION_ERROR,
                        error_message=error_msg
                    )
                    await self._publish_result(event, correlation_id)
                    await self._send_to_dlq(message, error_msg)
                    return

                logger.info(f"Processing: {request.exam_type} {request.task_type} [attempt={attempt_id}]")

                # 2. Call LLM evaluation service
                feedback: WritingFeedback = await evaluate_writing_with_local_llm(
                    request, correlation_id=correlation_id
                )

                # 3. Build success event
                event = WritingResultEvent(
                    status="success",
                    attempt_id=attempt_id,
                    response_id=response_id,
                    data=feedback
                )
                await self._publish_result(event, correlation_id)

            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)

                # Classify error code
                if "timeout" in error_msg.lower() or "Timeout" in error_type:
                    error_code = ErrorCode.LLM_TIMEOUT
                elif "connect" in error_msg.lower():
                    error_code = ErrorCode.LLM_CONNECTION_ERROR
                else:
                    error_code = ErrorCode.INTERNAL_ERROR

                logger.error(
                    f"Error [{error_code}]: {error_msg} [correlation_id={correlation_id}] [retry={retry_count}/{settings.MQ_MAX_RETRIES}]",
                    exc_info=True,
                )

                # Retry logic
                if retry_count < settings.MQ_MAX_RETRIES:
                    headers = dict(message.headers or {})
                    headers["x-retry-count"] = retry_count + 1

                    await self._exchange.publish(
                        aio_pika.Message(
                            body=message.body,
                            headers=headers,
                            correlation_id=correlation_id,
                            content_type="application/json",
                            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        ),
                        routing_key=settings.WRITING_ROUTING_KEY,
                    )
                    logger.info(f"Message requeued (retry {retry_count + 1}) [correlation_id={correlation_id}]")
                    return

                # Max retries exceeded → Send failure event + DLQ
                event = WritingResultEvent(
                    status="error",
                    attempt_id=attempt_id,
                    response_id=response_id,
                    error_code=error_code,
                    error_message=f"Failed after {settings.MQ_MAX_RETRIES} retries: {error_msg}"
                )
                await self._publish_result(event, correlation_id)
                await self._send_to_dlq(message, error_msg)

    async def _publish_result(
        self, 
        event: WritingResultEvent, 
        correlation_id: str
    ) -> None:
        """Publish result to the configured result routing key."""
        payload = event.model_dump()
        message = aio_pika.Message(
            body=json.dumps(payload).encode(),
            correlation_id=correlation_id,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        # Always publish to the results event key (EDA)
        await self._exchange.publish(
            message,
            routing_key=settings.WRITING_RESULT_ROUTING_KEY
        )
        logger.info(
            f"Result Event published to '{settings.WRITING_RESULT_ROUTING_KEY}' "
            f"[attempt={event.attempt_id}] [status={event.status}]"
        )
