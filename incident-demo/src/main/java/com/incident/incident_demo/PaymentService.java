package com.incident.incident_demo;

public class PaymentService {

    private final KafkaService kafkaService = new KafkaService();

    public void processPayment(){

        LogUtil.info("PaymentService","Processing payment...");
        kafkaService.publishPayment();
    }

}