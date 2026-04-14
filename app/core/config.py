from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM Configuration
    LLM_API_URL: str = ""
    LLM_MODEL_NAME: str = "" # Note: Có thể không cần cho HF Endpoint nếu token URL đã chứa endpoint.
    HF_TOKEN: str = ""
    LLM_TIMEOUT: int = 300  # seconds

    # RabbitMQ Connection
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    MQ_PREFETCH_COUNT: int = 1

    # Exchange
    MQ_EXCHANGE_NAME: str = "eventbus"
    MQ_EXCHANGE_TYPE: str = "topic"

    # Writing Queue
    WRITING_QUEUE_NAME: str = "writing.evaluate"
    WRITING_ROUTING_KEY: str = "exam.writing.submitted"
    WRITING_RESULT_ROUTING_KEY: str = "exam.writing.scored"

    # Dead Letter Queue (DLQ)
    WRITING_DLQ_NAME: str = "writing.evaluate.dlq"
    WRITING_DLQ_ROUTING_KEY: str = "exam.writing.submitted.dlq"
    MQ_MAX_RETRIES: int = 3
    MQ_MESSAGE_TTL: int = 120000  # milliseconds (2 minutes)

    # Health Check
    HEALTH_CHECK_PORT: int = 8081

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
