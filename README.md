# AI Language Evaluator — Microservice

An async Python microservice that evaluates IELTS/TOEIC writing essays using a local LLM, communicating via **RabbitMQ** message queue.

## Architecture

```
┌──────────────┐       ┌───────────────┐       ┌──────────────────┐       ┌────────────┐
│  Main BE     │──────>│  RabbitMQ     │──────>│  server-ai       │──────>│  Ollama    │
│  (Publisher) │       │  ai_service   │       │  (Python Worker) │       │  Local LLM │
│              │<──────│  exchange     │<──────│                  │<──────│            │
└──────────────┘       └───────────────┘       └──────────────────┘       └────────────┘
     gRPC/REST           Message Queue            async consumer           HTTP API
```

### Communication Pattern: RPC-over-RabbitMQ

1. **BE** publishes a JSON message to exchange `ai_service` with routing key `writing.evaluate`, including `correlation_id` and `reply_to` callback queue.
2. **Worker** consumes the message, calls the LLM via HTTP, and publishes the result back to the `reply_to` queue.
3. **BE** matches the response by `correlation_id`.

### Resilience Features

- **Dead Letter Queue (DLQ)**: Failed messages are retried up to `MQ_MAX_RETRIES` times before being moved to `writing.evaluate.dlq`.
- **Message TTL**: Messages expire after `MQ_MESSAGE_TTL` milliseconds.
- **Persistent Messages**: All messages use `delivery_mode=PERSISTENT` for durability.
- **Structured Error Codes**: `VALIDATION_ERROR`, `LLM_TIMEOUT`, `LLM_CONNECTION_ERROR`, `INTERNAL_ERROR`.
- **Health Check**: HTTP endpoint at `/health` on port `HEALTH_CHECK_PORT`.

## Project Structure

```
server-ai/
├── app/
│   ├── core/
│   │   ├── config.py            # Pydantic settings (env-based)
│   │   ├── health.py            # Health check HTTP server
│   │   └── logger.py            # Structured logging
│   ├── mq/
│   │   ├── __init__.py
│   │   ├── connection.py        # RabbitMQ connection manager
│   │   └── consumer.py          # Writing queue consumer + DLQ + retry
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── writing.py           # Pydantic request/response models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── evaluation_llm.py    # LLM evaluation business logic
│   │   └── prompt_template.txt  # IELTS prompt template
│   └── main.py                  # Entry point
├── .env                         # Environment config (not committed)
├── .gitignore
├── requirements.txt
├── test_publisher.py            # RabbitMQ test client
└── LICENSE
```

## Prerequisites

- **Python** 3.11+
- **Docker** (for RabbitMQ)
- **Ollama** running locally with the IELTS model

## Quick Start

### 1. Start RabbitMQ

```bash
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

Management UI: [http://localhost:15672](http://localhost:15672) (guest/guest)

### 2. Start Ollama with the IELTS model

```bash
ollama run hf.co/linhma139/Phi-3-IELTS-Scorer:Q4_K_M
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

Create a `.env` file (see `.env.example`):

```env
LLM_API_URL=http://localhost:11434/api/generate
LLM_MODEL_NAME=hf.co/linhma139/Phi-3-IELTS-Scorer:Q4_K_M
LLM_TIMEOUT=120

RABBITMQ_URL=amqp://guest:guest@localhost:5672/
MQ_PREFETCH_COUNT=1
MQ_EXCHANGE_NAME=ai_service
MQ_EXCHANGE_TYPE=direct

WRITING_QUEUE_NAME=writing.evaluate
WRITING_ROUTING_KEY=writing.evaluate

WRITING_DLQ_NAME=writing.evaluate.dlq
WRITING_DLQ_ROUTING_KEY=writing.evaluate.dlq
MQ_MAX_RETRIES=3
MQ_MESSAGE_TTL=120000

HEALTH_CHECK_PORT=8081
```

### 5. Run the worker

```bash
python app/main.py
```

Expected output:

```
INFO - Starting AI Microservice (RabbitMQ Worker)...
INFO - Health check server running on http://0.0.0.0:8081/health
INFO - Connected to RabbitMQ successfully.
INFO - Exchange: 'ai_service' (direct) | Queue: 'writing.evaluate' | DLQ: 'writing.evaluate.dlq' | ...
INFO - AI Worker is running. Waiting for messages...
```

### 6. Test

```bash
python test_publisher.py
```

### 7. Health check

```bash
curl http://localhost:8081/health
# {"status": "healthy", "rabbitmq": "connected"}
```

## Message Contract

### Request (publish to `ai_service` exchange, routing key `writing.evaluate`)

```json
{
  "exam_type": "IELTS",
  "task_type": "Task 2",
  "question": "Some people think...",
  "content": "It is often argued...",
  "target_score": 7.0
}
```

**Required AMQP properties:**
- `correlation_id`: UUID for request-response matching
- `reply_to`: callback queue name
- `content_type`: `application/json`

### Response (received on callback queue)

**Success:**
```json
{
  "status": "success",
  "data": {
    "overall_score": 7.0,
    "sub_scores": {
      "Task Achievement": 7.0,
      "Coherence & Cohesion": 7.0,
      "Lexical Resource": 6.5,
      "Grammatical Range & Accuracy": 7.0
    },
    "detailed_feedback": "...",
    "corrected_version": "",
    "corrections": []
  }
}
```

**Error:**
```json
{
  "status": "error",
  "error_code": "LLM_TIMEOUT",
  "error": "Failed after 3 retries: Ollama request timed out"
}
```

**Error codes:** `VALIDATION_ERROR` | `LLM_TIMEOUT` | `LLM_CONNECTION_ERROR` | `INTERNAL_ERROR`

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Runtime | Python 3.11+ / asyncio |
| Message Queue | RabbitMQ (aio-pika) |
| HTTP Client | httpx (async, shared pool) |
| Schema Validation | Pydantic v2 |
| Config | pydantic-settings + .env |
| Health Check | aiohttp |
| LLM | Ollama (Phi-3-IELTS-Scorer) |

## License

MIT
