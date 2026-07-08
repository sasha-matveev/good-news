package com.goodnews.backendjava.service;

public interface SmtpEmailAdapter {

    void send(TestEmailMessage message, SmtpConnectionSettings connectionSettings);

    record TestEmailMessage(String sender, String recipient, String subject, String htmlBody) {}

    record SmtpConnectionSettings(
        String host,
        int port,
        String username,
        String password,
        String securityMode
    ) {}
}
