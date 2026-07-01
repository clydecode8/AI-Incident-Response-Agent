package com.incident.incident_demo;

public class IncidentDemoApplication {
    public static void main(String[] args) {

        String scenario = args.length > 0 ? args[0] : "";

        try {
            if (scenario.equals("kafka")) {
                PaymentService ps = new PaymentService();
                ps.processPayment();

            } else if (scenario.equals("null-user")) {
                UserService us = new UserService();
                us.sendWelcomeEmail();

            } else {
                System.out.println("Unknown scenario: " + scenario);
            }

        } catch (Exception ex) {
            String service = scenario.equals("null-user") ? "UserService" : "PaymentService";
            LogUtil.error(service, ex.toString());
            ex.printStackTrace();
        }
    }
}