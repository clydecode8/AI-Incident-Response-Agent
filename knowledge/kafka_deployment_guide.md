# Kafka Deployment Guide

Kafka must be healthy before payment-related deployments.

Pre-deployment checks:
1. Verify broker health.
2. Check topic availability.
3. Confirm producer timeout setting.
4. Confirm network connectivity between services and Kafka.

Recommended producer timeout: 10 seconds.