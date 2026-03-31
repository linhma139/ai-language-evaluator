"""
Test publisher for AI Microservice RabbitMQ worker (Event-Driven version).
Usage: python test_publisher.py
"""
import json
import uuid
import asyncio
import aio_pika

# RabbitMQ Configuration
RABBITMQ_URL = "amqp://guest:guest@localhost:5672/"
EXCHANGE_NAME = "ai_service"
ROUTING_KEY = "writing.evaluate"
RESULT_ROUTING_KEY = "writing.result"
RESULT_QUEUE_NAME = "writing.result"

SAMPLE_QUESTION = (
    "Some people think that the best way to reduce crime is to give longer prison "
    "sentences. Others, however, believe there are better alternative ways of "
    "reducing crime. Discuss both views and give your opinion."
)

SAMPLE_ESSAY = (
    "It is often argued that imposing longer prison sentences is the most effective "
    "method to reduce crime rates. However, others contend that alternative approaches, "
    "such as education and rehabilitation programs, are more effective. This essay will "
    "discuss both perspectives before presenting my own opinion.\n\n"
)


async def test_event_driven():
    print("=" * 60)
    print("🧪 AI Microservice - RabbitMQ Event-Driven Test")
    print("=" * 60)

    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
    except Exception as e:
        print(f"❌ Failed to connect to RabbitMQ: {e}")
        return

    async with connection:
        channel = await connection.channel()

        # 1. Declare Exchange
        exchange = await channel.declare_exchange(
            EXCHANGE_NAME,
            type=aio_pika.ExchangeType.DIRECT,
            durable=True,
        )

        # 2. Declare and Bind Result Queue (Where BE listens)
        result_queue = await channel.declare_queue(RESULT_QUEUE_NAME, durable=True)
        await result_queue.bind(exchange, routing_key=RESULT_ROUTING_KEY)

        correlation_id = str(uuid.uuid4())
        attempt_id = str(uuid.uuid4())

        request_payload = {
            "attempt_id": attempt_id,
            "response_id": str(uuid.uuid4()),
            "exam_type": "IELTS",
            "task_type": "Task 2",
            "question": SAMPLE_QUESTION,
            "content": SAMPLE_ESSAY,
            "target_score": 7.0,
        }

        print(f"\n📤 Publishing WritingRequest Event...")
        print(f"   Exchange: {EXCHANGE_NAME}")
        print(f"   Routing key: {ROUTING_KEY}")
        print(f"   Attempt ID: {attempt_id}")
        print(f"   Correlation ID: {correlation_id}")
        print("-" * 60)

        # 3. Publish without reply_to (Pure Event)
        await exchange.publish(
            aio_pika.Message(
                body=json.dumps(request_payload).encode(),
                correlation_id=correlation_id,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=ROUTING_KEY,
        )

        print(f"⏳ Waiting for Result Event on '{RESULT_ROUTING_KEY}'...\n")

        # 4. Listen for the result on the shared result queue
        async with result_queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    result = json.loads(message.body.decode())
                    
                    # Filter by correlation_id or attempt_id to ensure it's our message
                    if message.correlation_id == correlation_id or result.get("attempt_id") == attempt_id:
                        print("✅ Result Event received!")
                        print("=" * 60)

                        if result["status"] == "success":
                            data = result["data"]
                            print(f"📊 Overall Score: {data['overall_score']}")
                            print(f"\n📋 Sub Scores:")
                            for key, val in data.get("sub_scores", {}).items():
                                print(f"   • {key}: {val}")
                            print(f"\n📝 Detailed Feedback:")
                            print(f"   {data['detailed_feedback'][:300]}...")
                        else:
                            print(f"❌ Error [{result.get('error_code')}]: {result.get('error_message')}")

                        print("=" * 60)
                        return  # Done


if __name__ == "__main__":
    try:
        asyncio.run(test_event_driven())
    except KeyboardInterrupt:
        print("\nTest cancelled by user.")
