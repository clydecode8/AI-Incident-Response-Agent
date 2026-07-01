# Payment Service Overview

PaymentService handles payment processing.

Main dependencies:
- Kafka for publishing payment events
- OrderService for order status updates
- PostgreSQL for payment records

PaymentService publishes payment events to Kafka topic: payment-events.
If Kafka is unavailable, payment event publishing may fail.