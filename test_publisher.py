"""
Test publisher for AI Microservice RabbitMQ worker.
Usage: python test_publisher.py

Requires:
  - RabbitMQ running at localhost:5672
  - Worker running: python app/main.py
"""
import json
import uuid
import asyncio
import aio_pika

# Match the env config (or read from .env if needed)
RABBITMQ_URL = "amqp://guest:guest@localhost:5672/"
EXCHANGE_NAME = "ai_service"
ROUTING_KEY = "writing.evaluate"

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


async def test_rpc():
    print("=" * 60)
    print("🧪 AI Microservice - RabbitMQ Test Publisher")
    print("=" * 60)

    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()

        # Declare the same exchange the worker uses
        exchange = await channel.declare_exchange(
            EXCHANGE_NAME,
            type=aio_pika.ExchangeType.DIRECT,
            durable=True,
        )

        # Declare an exclusive callback queue for receiving the response
        callback_queue = await channel.declare_queue("", exclusive=True)
        correlation_id = str(uuid.uuid4())

        request_payload = {
            "exam_type": "IELTS",
            "task_type": "Task 2",
            "question": SAMPLE_QUESTION,
            "content": SAMPLE_ESSAY,
            "target_score": 7.0,
        }

        print(f"\n📤 Publishing WritingRequest...")
        print(f"   Exchange: {EXCHANGE_NAME}")
        print(f"   Routing key: {ROUTING_KEY}")
        print(f"   Exam: {request_payload['exam_type']} | Task: {request_payload['task_type']}")
        print(f"   Essay length: {len(SAMPLE_ESSAY)} chars")
        print(f"   Correlation ID: {correlation_id}")
        print("-" * 60)

        # Publish the request via the named exchange
        await exchange.publish(
            aio_pika.Message(
                body=json.dumps(request_payload).encode(),
                correlation_id=correlation_id,
                reply_to=callback_queue.name,
                content_type="application/json",
            ),
            routing_key=ROUTING_KEY,
        )

        print("⏳ Waiting for LLM response (this may take 10-60s)...\n")

        # Wait for the response on callback queue
        async with callback_queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    if message.correlation_id == correlation_id:
                        result = json.loads(message.body.decode())
                        print("✅ Response received!")
                        print("=" * 60)

                        if result["status"] == "success":
                            data = result["data"]
                            print(f"📊 Overall Score: {data['overall_score']}")
                            print(f"\n📋 Sub Scores:")
                            for key, val in data.get("sub_scores", {}).items():
                                print(f"   • {key}: {val}")
                            print(f"\n📝 Detailed Feedback:")
                            print(f"   {data['detailed_feedback'][:500]}...")
                            if data.get("corrected_version"):
                                print(f"\n✏️ Corrected Version: {data['corrected_version'][:200]}...")
                            corrections = data.get("corrections", [])
                            if corrections:
                                print(f"\n🔍 Corrections ({len(corrections)}):")
                                for c in corrections[:3]:
                                    print(f"   [{c['error_type']}] '{c['original_text']}' → '{c['corrected_text']}'")
                        else:
                            print(f"❌ Error: {result.get('error', 'Unknown error')}")

                        print("=" * 60)
                        return  # Done


if __name__ == "__main__":
    asyncio.run(test_rpc())
