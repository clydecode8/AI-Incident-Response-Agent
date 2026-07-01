package com.incident.incident_demo;

import java.io.FileWriter;
import java.io.IOException;
import java.time.LocalDateTime;

public class LogUtil {

    private static final String LOG_FILE = "logs/application.log";

    public static void info(String service, String message) {
        write("INFO", service, message);
    }

    public static void error(String service, String message) {
        write("ERROR", service, message);
    }

    private static void write(String level, String service, String message) {
        try (FileWriter writer = new FileWriter(LOG_FILE, true)) {
            writer.write(
                String.format(
                    "%s %s [main] com.incident.incident_demo.%s - %s%n",
                    LocalDateTime.now(),
                    level,
                    service,
                    message
                )
            );
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

}