#!/usr/bin/env python3
"""
Example demonstrating resilient Kafka messaging patterns with error handling and retry mechanisms.

This script showcases:
1. Resilient producer with retry logic and error handling
2. Resilient consumer with a dead letter queue pattern
3. Error simulation and recovery scenarios
4. Monitoring and observability features

Usage:
    python example_resilient_messaging.py --mode producer
    python example_resilient_messaging.py --mode consumer
    python example_resilient_messaging.py --mode error-demo
"""

import argparse
import os
import time
import threading
from datetime import datetime

from resilient_producer import ResilientProducer
from resilient_consumer import ResilientConsumer, RetryableException


def run_resilient_producer_demo():
    """Demonstrate a resilient producer with various message types and error scenarios."""
    print("🚀 Starting Resilient Producer Demo")
    print("=" * 50)

    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    topic = os.environ.get("KAFKA_TOPIC", "resilient-demo-topic")

    # Sample messages with different characteristics
    messages = [
        # Normal messages
        {"id": 1, "event_type": "user_created", "user_id": "user123", "timestamp": time.time()},
        {"id": 2, "event_type": "user_updated", "user_id": "user123",
         "data": {"name": "John Doe", "email": "john@example.com"}},
        {"id": 3, "event_type": "order_placed", "order_id": "order456", "user_id": "user123", "amount": 99.99},

        # Messages that might cause processing errors in consumer
        {"id": 4, "event_type": "error_test", "user_id": "user123", "data": "This will cause retriable error"},
        {"id": 5, "event_type": "fatal_error", "user_id": "user123", "data": "This will cause non-retriable error"},

        # Batch processing test messages
        {"id": 6, "event_type": "batch_test", "batch_id": "batch1", "data": "Batch message 1"},
        {"id": 7, "event_type": "batch_test", "batch_id": "batch1", "data": "Batch message 2"},
        {"id": 8, "event_type": "batch_error", "batch_id": "batch1", "data": "This will cause batch error"},

        # High volume messages
        *[{"id": 100 + i, "event_type": "high_volume", "sequence": i, "data": f"Volume message {i}"}
          for i in range(10)]
    ]

    try:
        with ResilientProducer(bootstrap_servers, retries=3, retry_delay=1.0) as producer:
            print(f"📤 Sending {len(messages)} messages to topic: {topic}")

            successful_sends = 0
            failed_sends = 0

            for i, message in enumerate(messages, 1):
                try:
                    # Use the appropriate key for partitioning
                    key = message.get("user_id") or message.get("order_id") or message.get("batch_id")

                    print(f"\n[{i}/{len(messages)}] Sending: {message['event_type']} (key: {key})")

                    # Send it with retry logic
                    metadata = producer.send_message_with_retry(topic, message, key=key)

                    print(f"✅ Success: partition={metadata.partition}, offset={metadata.offset}")
                    successful_sends += 1

                    # Small delay between messages
                    time.sleep(0.1)

                except Exception as e:
                    print(f"❌ Failed: {e}")
                    failed_sends += 1

            # Demonstrate async sending with callbacks
            print(f"\n📤 Sending async messages with callbacks...")

            def send_callback(error, metadata):
                if error:
                    print(f"❌ Async send failed: {error}")
                else:
                    print(f"✅ Async send succeeded: partition={metadata.partition}, offset={metadata.offset}")

            async_messages = [
                {"id": 200, "event_type": "async_test", "data": "Async message 1"},
                {"id": 201, "event_type": "async_test", "data": "Async message 2"},
            ]

            for message in async_messages:
                producer.send_message_async(topic, message, callback=send_callback)

            # Ensure all async messages are sent
            producer.flush()

            print(f"\n📊 Producer Summary:")
            print(f"   ✅ Successful sends: {successful_sends}")
            print(f"   ❌ Failed sends: {failed_sends}")
            print(f"   📈 Success rate: {successful_sends / (successful_sends + failed_sends) * 100:.1f}%")

    except KeyboardInterrupt:
        print("\n🛑 Producer stopped by user")
    except Exception as e:
        print(f"\n💥 Producer error: {e}")


def run_resilient_consumer_demo():
    """Demonstrate resilient consumer with error handling and DLQ."""
    print("🔄 Starting Resilient Consumer Demo")
    print("=" * 50)

    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    topic = os.environ.get("KAFKA_TOPIC", "resilient-demo-topic")
    dlq_topic = os.environ.get("KAFKA_DLQ_TOPIC", "resilient-demo-topic-dlq")
    group_id = "resilient-demo-consumer"

    # Message processing statistics
    stats = {
        "processed": 0,
        "retried": 0,
        "sent_to_dlq": 0,
        "errors": 0
    }
    stats_lock = threading.Lock()

    def process_message(message):
        """Message processing function with simulated errors."""
        with stats_lock:
            print(f"\n📨 Processing message: key={message.key}, partition={message.partition}, offset={message.offset}")

            if isinstance(message.value, dict):
                event_type = message.value.get("event_type")
                message_id = message.value.get("id")

                print(f"   Event: {event_type} (ID: {message_id})")

                # Simulate different error scenarios
                if event_type == "error_test":
                    stats["retried"] += 1
                    print("   ⚠️  Simulating retriable error...")
                    raise RetryableException(f"Simulated retriable error for message {message_id}")

                elif event_type == "fatal_error":
                    stats["errors"] += 1
                    print("   💥 Simulating fatal error...")
                    raise ValueError(f"Simulated fatal error for message {message_id}")

                # Normal processing
                print(f"   ✅ Successfully processed {event_type} event")
                stats["processed"] += 1

            else:
                print(f"   ✅ Processed plain text: {message.value}")
                stats["processed"] += 1

    def process_batch(messages):
        """Batch processing function with simulated errors."""
        with stats_lock:
            print(f"\n📦 Processing batch of {len(messages)} messages")

            for message in messages:
                if isinstance(message.value, dict):
                    event_type = message.value.get("event_type")

                    if event_type == "batch_error":
                        stats["errors"] += 1
                        print("   💥 Simulating batch processing error...")
                        raise RetryableException("Simulated batch processing error")

            print(f"   ✅ Batch processed successfully ({len(messages)} messages)")
            stats["processed"] += len(messages)

    def print_stats():
        """Print processing statistics periodically."""
        while True:
            time.sleep(10)
            with stats_lock:
                print(f"\n📊 Consumer Stats: processed={stats['processed']}, "
                      f"retried={stats['retried']}, dlq={stats['sent_to_dlq']}, "
                      f"errors={stats['errors']}")

    try:
        # Start a statistics reporting thread
        stats_thread = threading.Thread(target=print_stats, daemon=True)
        stats_thread.start()

        print(f"🔄 Starting consumer for topic: {topic}")
        print(f"🗂️  Dead letter queue: {dlq_topic}")
        print(f"👥 Consumer group: {group_id}")
        print("📝 Press Ctrl+C to stop\n")

        # Choose processing mode based on environment variable
        batch_mode = os.environ.get("BATCH_MODE", "false").lower() == "true"

        with ResilientConsumer(bootstrap_servers, [topic], group_id, dlq_topic) as consumer:

            if batch_mode:
                print("🔄 Running in BATCH mode")
                consumer.process_messages_batch(
                    process_batch,
                    batch_size=5,
                    batch_timeout=3.0,
                    max_retries=2
                )
            else:
                print("🔄 Running in SINGLE MESSAGE mode")
                consumer.process_messages(
                    process_message,
                    max_retries=2,
                    retry_delay=1.0
                )

    except KeyboardInterrupt:
        print("\n🛑 Consumer stopped by user")
        with stats_lock:
            print(f"\n📊 Final Stats: processed={stats['processed']}, "
                  f"retried={stats['retried']}, dlq={stats['sent_to_dlq']}, "
                  f"errors={stats['errors']}")
    except Exception as e:
        print(f"\n💥 Consumer error: {e}")


def run_error_demonstration():
    """Demonstrate error handling capabilities and recovery scenarios."""
    print("🧪 Starting Error Handling Demonstration")
    print("=" * 50)

    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    topic = os.environ.get("KAFKA_TOPIC", "error-demo-topic")
    dlq_topic = os.environ.get("KAFKA_DLQ_TOPIC", "error-demo-topic-dlq")

    # Scenario 1: Producer retry scenarios
    print("\n🎯 Scenario 1: Producer Error Handling")
    print("-" * 30)

    error_messages = [
        {"id": 1, "scenario": "normal", "data": "This should succeed"},
        {"id": 2, "scenario": "timeout_simulation", "data": "This might timeout"},
        {"id": 3, "scenario": "network_error", "data": "This might have network issues"},
    ]

    try:
        with ResilientProducer(bootstrap_servers, retries=2, retry_delay=0.5) as producer:
            for message in error_messages:
                print(f"\n📤 Testing: {message['scenario']}")
                try:
                    metadata = producer.send_message_with_retry(topic, message, key=str(message['id']))
                    print(
                        f"✅ Success: {message['scenario']} -> partition={metadata.partition}, offset={metadata.offset}")
                except Exception as e:
                    print(f"❌ Failed: {message['scenario']} -> {e}")

                time.sleep(1)
    except Exception as e:
        print(f"💥 Producer demo error: {e}")

    # Scenario 2: Consumer error handling and DLQ
    print("\n🎯 Scenario 2: Consumer Error Handling & DLQ")
    print("-" * 30)

    # First, send messages that will cause different types of errors
    test_messages = [
        {"id": 100, "event_type": "normal", "data": "Normal message"},
        {"id": 101, "event_type": "error_test", "data": "Will cause retriable error"},
        {"id": 102, "event_type": "fatal_error", "data": "Will cause fatal error"},
        {"id": 103, "event_type": "normal", "data": "Another normal message"},
    ]

    # Send test messages
    try:
        with ResilientProducer(bootstrap_servers) as producer:
            print("📤 Sending test messages for error scenarios...")
            for message in test_messages:
                metadata = producer.send_message_with_retry(topic, message, key=str(message['id']))
                print(f"✅ Sent: {message['event_type']} -> offset={metadata.offset}")
                time.sleep(0.1)
    except Exception as e:
        print(f"💥 Failed to send test messages: {e}")
        return

    # Process messages with error handling
    print("\n🔄 Processing messages with error handling...")

    processed_count = 0
    error_count = 0

    def error_demo_handler(message):
        nonlocal processed_count, error_count

        print(f"\n📨 Processing: {message.value}")

        if isinstance(message.value, dict):
            event_type = message.value.get("event_type")

            if event_type == "error_test":
                error_count += 1
                print("   ⚠️  Raising retriable error (will retry then go to DLQ)")
                raise RetryableException("Demo retriable error")

            elif event_type == "fatal_error":
                error_count += 1
                print("   💥 Raising fatal error (will go directly to DLQ)")
                raise ValueError("Demo fatal error")

            else:
                processed_count += 1
                print(f"   ✅ Successfully processed: {event_type}")
        else:
            processed_count += 1
            print("   ✅ Successfully processed text message")

    try:
        with ResilientConsumer(bootstrap_servers, [topic], "error-demo-group", dlq_topic) as consumer:
            print("🔄 Starting error demonstration consumer...")
            print("⏱️  Will process for 15 seconds then stop...")

            # Use a timer to stop processing after a short time without raising exceptions in a thread
            def stop_processing():
                time.sleep(15)
                # Request graceful shutdown
                try:
                    if hasattr(consumer, "close") and callable(getattr(consumer, "close")):
                        consumer.close()
                except Exception:
                    # Best-effort shutdown; avoid raising from background thread
                    pass

            timer_thread = threading.Thread(target=stop_processing, daemon=True)
            timer_thread.start()

            consumer.process_messages(error_demo_handler, max_retries=1, retry_delay=0.5)

    except KeyboardInterrupt:
        print("\n⏹️  Error demonstration completed")
        print(f"\n📊 Error Demo Results:")
        print(f"   ✅ Processed successfully: {processed_count}")
        print(f"   ⚠️  Errors encountered: {error_count}")
        print(f"   📋 Check DLQ topic '{dlq_topic}' for failed messages")

    except Exception as e:
        print(f"💥 Error demonstration failed: {e}")
    else:
        # Graceful shutdown path (no KeyboardInterrupt raised)
        print("\n⏹️  Error demonstration completed")
        print(f"\n📊 Error Demo Results:")
        print(f"   ✅ Processed successfully: {processed_count}")
        print(f"   ⚠️  Errors encountered: {error_count}")
        print(f"   📋 Check DLQ topic '{dlq_topic}' for failed messages")

    # Scenario 3: Monitoring DLQ
    print(f"\n🎯 Scenario 3: Monitoring Dead Letter Queue")
    print("-" * 30)

    try:
        print(f"🔍 Checking DLQ topic: {dlq_topic}")

        def dlq_monitor(message):
            print(f"\n📋 DLQ Message found:")
            if isinstance(message.value, dict):
                dlq_data = message.value
                print(
                    f"   📍 Original: {dlq_data.get('original_topic')}:{dlq_data.get('original_partition')}:{dlq_data.get('original_offset')}")
                print(f"   ❌ Error: {dlq_data.get('error_type')} - {dlq_data.get('error_reason')}")
                print(f"   ⏰ Failed at: {datetime.fromtimestamp(dlq_data.get('failed_at', 0))}")
                print(f"   🗂️  Consumer group: {dlq_data.get('consumer_group')}")
            else:
                print(f"   📄 Content: {message.value}")

        with ResilientConsumer(bootstrap_servers, [dlq_topic], "dlq-monitor-group") as dlq_consumer:
            print("🔍 Monitoring DLQ for 10 seconds...")

            # Monitor for a short time without raising exceptions in a thread
            def stop_monitoring():
                time.sleep(10)
                try:
                    if hasattr(dlq_consumer, "close") and callable(getattr(dlq_consumer, "close")):
                        dlq_consumer.close()
                except Exception:
                    pass

            timer_thread = threading.Thread(target=stop_monitoring, daemon=True)
            timer_thread.start()

            dlq_consumer.process_messages(dlq_monitor)

    except KeyboardInterrupt:
        print("\n⏹️  DLQ monitoring completed")
    except Exception as e:
        print(f"💥 DLQ monitoring error: {e}")
    else:
        print("\n⏹️  DLQ monitoring completed")

    print("\n🎯 Error Handling Demonstration Complete!")
    print("✨ The resilient messaging patterns successfully handled various error scenarios")


def main():
    """Main function to run different demonstration modes."""
    parser = argparse.ArgumentParser(description="Resilient Kafka Messaging Demo")
    parser.add_argument(
        "--mode",
        choices=["producer", "consumer", "error-demo"],
        default="error-demo",
        help="Demo mode to run"
    )

    args = parser.parse_args()

    print("🌟 Resilient Kafka Messaging Patterns Demo")
    print(f"📊 Mode: {args.mode}")
    print(f"🔗 Kafka: {os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')}")
    print(f"📂 Topic: {os.environ.get('KAFKA_TOPIC', 'resilient-demo-topic')}")
    print(f"🗂️  DLQ: {os.environ.get('KAFKA_DLQ_TOPIC', 'resilient-demo-topic-dlq')}")
    print()

    try:
        if args.mode == "producer":
            run_resilient_producer_demo()
        elif args.mode == "consumer":
            run_resilient_consumer_demo()
        elif args.mode == "error-demo":
            run_error_demonstration()
    except KeyboardInterrupt:
        print("\n👋 Demo stopped by user")
    except Exception as e:
        print(f"\n💥 Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
