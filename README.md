# AI Language Evaluator — Microservice

An async Python microservice that evaluates IELTS/TOEIC writing essays using a local LLM, communicating via **RabbitMQ** message queue.

## Architecture: Event-Driven Architecture (EDA)

The microservice follows a pure asynchronous, event-driven pattern. It doesn't use the standard request-response RPC; instead, it consumes "Evaluation Request" events and publishes "Evaluation Result" events.

```
┌──────────────┐       ┌───────────────┐       ┌──────────────────┐       ┌────────────┐
│  Main BE     │──────>│  RabbitMQ     │──────>│  server-ai       │──────>│  Ollama    │
│  (Publisher) │       │  writing.eval │       │  (Python Worker) │       │  Local LLM │
└──────────────┘       └──────┬────────┘       └────────┬─────────┘       └────────────┘
                              │                         │
┌──────────────┐              │                         │
│  Main BE     │<─────────────┴─────────────────────────┘
│  (Subscriber)│         writing.result
└──────────────┘         (Result Event)
```

### Communication Flow

1. **BE** publishes a `WritingRequest` event to the `ai_service` exchange with routing key `writing.evaluate`.
2. **Worker** consumes the event, calls the LLM, and publishes a `WritingResultEvent` to the same exchange with routing key `writing.result`.
3. **BE** (or any other service) listens to `writing.result` to process the feedback.

### Resilience Features

- **Dead Letter Queue (DLQ)**: Failed messages are retried up to `MQ_MAX_RETRIES` times before being moved to `writing.evaluate.dlq`.
- **Automatic Error Reporting**: Even if a fatal error occurs (validation, timeout), a "Failure Event" is published back to BE so it can update the user's status.
- **Message TTL**: Messages expire after `MQ_MESSAGE_TTL` milliseconds if not consumed.
- **Persistent Messages**: All messages use `delivery_mode=PERSISTENT` for durability.
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
│   │   ├── connection.py        # RabbitMQ connection manager
│   │   └── consumer.py          # Pure EDA consumer + DLQ + retry
│   ├── schemas/
│   │   └── writing.py           # Pydantic Request/Feedback/Event models
│   ├── services/
│   │   ├── evaluation_llm.py    # LLM evaluation logic
│   │   └── prompt_template.txt  # IELTS prompt template
│   └── main.py                  # Entry point
├── test_publisher.py            # EDA test client
└── README.md
```

## Quick Start

### 1. Start RabbitMQ

```bash
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

### 2. Run the worker

```bash
python app/main.py
```

### 3. Test with Event-Driven flow

```bash
python test_publisher.py
```

## Message Contract (v2 - EDA)

### Request Event (`writing.evaluate`)

```json
{
  "attempt_id": "uuid-v4",
  "response_id": "uuid-v4",
  "exam_type": "IELTS",
  "task_type": "Task 2",
  "question": "Some people think...",
  "content": "It is often argued...",
  "target_score": 7.0
}
```

### Result Event (`writing.result`)

**Success Payload:**
```json
{
  "status": "success",
  "attempt_id": "uuid-v4",
  "response_id": "uuid-v4",
  "data": {
    "overall_score": 7.5,
    "sub_scores": {
      "Task Achievement": 7.5,
      "Coherence & Cohesion": 8.0,
      "Lexical Resource": 7.0,
      "Grammatical Range & Accuracy": 7.5
    },
    "detailed_feedback": "...",
    "corrected_version": "...",
    "corrections": [...]
  }
}
```

**Failure Payload:**
```json
{
  "status": "error",
  "attempt_id": "uuid-v4",
  "response_id": "uuid-v4",
  "error_code": "LLM_TIMEOUT",
  "error_message": "Failed after 3 retries: Ollama request timed out"
}
```

**Error codes:** `VALIDATION_ERROR` | `LLM_TIMEOUT` | `LLM_CONNECTION_ERROR` | `INTERNAL_ERROR`

## Tech Stack

- **Runtime**: Python 3.11+ / asyncio
- **Queue**: RabbitMQ (aio-pika)
- **Validation**: Pydantic v2
- **Config**: Pydantic-settings
- **LLM**: Ollama (Phi-3-IELTS-Scorer)
