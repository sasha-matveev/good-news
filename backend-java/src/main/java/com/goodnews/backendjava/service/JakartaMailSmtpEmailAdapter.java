package com.goodnews.backendjava.service;

import jakarta.mail.Message;
import jakarta.mail.Session;
import jakarta.mail.Transport;
import jakarta.mail.internet.InternetAddress;
import jakarta.mail.internet.MimeMessage;
import java.util.Properties;
import org.springframework.stereotype.Component;

@Component
public class JakartaMailSmtpEmailAdapter implements SmtpEmailAdapter {

    @Override
    public void send(TestEmailMessage message, SmtpConnectionSettings connectionSettings) {
        Properties properties = new Properties();
        properties.setProperty("mail.smtp.host", connectionSettings.host());
        properties.setProperty("mail.smtp.port", Integer.toString(connectionSettings.port()));
        properties.setProperty("mail.smtp.auth", Boolean.toString(hasText(connectionSettings.username())));
        properties.setProperty("mail.smtp.starttls.enable", Boolean.toString("starttls".equals(connectionSettings.securityMode())));
        properties.setProperty("mail.smtp.ssl.enable", Boolean.toString("ssl".equals(connectionSettings.securityMode())));

        Session session = Session.getInstance(properties);
        try {
            MimeMessage mimeMessage = new MimeMessage(session);
            mimeMessage.setFrom(new InternetAddress(message.sender()));
            mimeMessage.setRecipients(Message.RecipientType.TO, InternetAddress.parse(message.recipient()));
            mimeMessage.setSubject(message.subject(), "UTF-8");
            mimeMessage.setContent(message.htmlBody(), "text/html; charset=UTF-8");

            try (Transport transport = session.getTransport("smtp")) {
                if (hasText(connectionSettings.username())) {
                    transport.connect(
                        connectionSettings.host(),
                        connectionSettings.port(),
                        connectionSettings.username(),
                        connectionSettings.password() == null ? "" : connectionSettings.password()
                    );
                } else {
                    transport.connect();
                }
                transport.sendMessage(mimeMessage, mimeMessage.getAllRecipients());
            }
        } catch (Exception exception) {
            throw new IllegalStateException(exception.getMessage(), exception);
        }
    }

    private boolean hasText(String value) {
        return value != null && !value.isBlank();
    }
}
