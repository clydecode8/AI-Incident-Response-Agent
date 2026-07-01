package com.incident.incident_demo;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;

public class MetricsUtil {

    // Simulates Grafana/Prometheus metrics.
    // In production, these metrics would be collected by Prometheus
    // and visualized in Grafana. Here we simply write them to JSON.
    private static final String METRICS_FILE = "metrics/metrics.json";

    public static void writeMetrics(
            String service,
            double cpuUsage,
            double memoryUsage,
            int latencyMs,
            double errorRate,
            int requestsPerSecond,
            String serviceStatus
    ) {

        try {

            File directory = new File("metrics");
            if (!directory.exists()) {
                directory.mkdirs();
            }

            FileWriter writer = new FileWriter(METRICS_FILE, false);

            writer.write("{\n");
            writer.write("  \"service\": \"" + service + "\",\n");
            writer.write("  \"cpu_usage\": " + cpuUsage + ",\n");
            writer.write("  \"memory_usage\": " + memoryUsage + ",\n");
            writer.write("  \"latency_ms\": " + latencyMs + ",\n");
            writer.write("  \"error_rate\": " + errorRate + ",\n");
            writer.write("  \"requests_per_second\": " + requestsPerSecond + ",\n");
            writer.write("  \"service_status\": \"" + serviceStatus + "\"\n");
            writer.write("}");

            writer.close();

        } catch (IOException e) {
            e.printStackTrace();
        }

    }

}