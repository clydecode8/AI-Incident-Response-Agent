# Kafka Timeout Troubleshooting Guide

KafkaTimeoutException means the service failed to publish a message to Kafka.

Common causes:
- Kafka broker unavailable
- Topic does not exist
- Network timeout
- Producer timeout too low
- Broker overloaded

Recommended actions:
1. Check Kafka broker health.
2. Verify topic configuration.
3. Check network connectivity.
4. Increase producer timeout.
5. Review retry configuration.