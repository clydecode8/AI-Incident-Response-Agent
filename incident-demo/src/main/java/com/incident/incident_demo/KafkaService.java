package com.incident.incident_demo;

public class KafkaService {

    public void publishPayment(){

        LogUtil.info("Kafka", "Publishing payment event...");

        // Simulated Grafana metrics
        MetricsUtil.writeMetrics(
                "PaymentService",
                91.3,      // CPU %
                78.5,      // Memory %
                6500,      // Latency (ms)
                15.8,      // Error rate (%)
                37,        // Requests/sec
                "DEGRADED"
        );
        
        throw new RuntimeException("KafkaTimeoutException: Broker unavailable");
    }

}