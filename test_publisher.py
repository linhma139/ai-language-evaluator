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
EXCHANGE_NAME = "eventbus"
ROUTING_KEY = "exam.writing.submitted"
RESULT_ROUTING_KEY = "exam.writing.scored"
RESULT_QUEUE_NAME = "test.exam.writing.scored"

SAMPLE_QUESTION = (
    "Some people say that the education system is the only critical factor to development of a country. To what extent do you agree or disagree with this statement?"
)

SAMPLE_ESSAY = """Education plays a vital role in the development of a country. Therefore, some people think that the education system is the only important factor to the development of a country and they may be right.

Education is the foundation of well developed society. It is rightly said, ‘education is a ladder for success’. If all the people of any country are educated then they becomes broadminded, civilized and progressive. An educated society improves the standard of life as well.

Besides this, education also creates a good employment opportunity and therefore country does not have to suffer from big problems like unemployment. Educated peoples are more aware of problems such as pollution and many more. A country becomes technologically advanced because of educated people.
Not only this, but also by giving importance to education, the nations can get rid of problems like iliteracy, poverty, unemployment and population growth that delay the progress of a nation. The crime rate can also be kept under check. The standard of living of the people will go up. If the nations wants to be progressive it is very important that the people are more educated and progressive. Any country can become more technologically advanced and developed because of education.

However, there are other factors that also play an important role in the development of a country. Such as governments have to encouraged people to do so._

In conclusion, I would like to say that a good education system will lead to a developed country."""


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
            type=aio_pika.ExchangeType.TOPIC,
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
