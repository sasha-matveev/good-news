package com.goodnews.backendjava.service;

import com.goodnews.backendjava.config.EmailProperties;
import com.goodnews.backendjava.config.GoodNewsProperties;
import jakarta.mail.Message;
import jakarta.mail.Session;
import jakarta.mail.Transport;
import jakarta.mail.internet.InternetAddress;
import jakarta.mail.internet.MimeMessage;
import java.util.Properties;
import org.springframework.stereotype.Component;

@Component
public class JakartaMailSmtpEmailAdapter implements SmtpEmailAdapter {

    private final EmailProperties properties;

    public JakartaMailSmtpEmailAdapter(GoodNewsProperties properties) {
        this.properties = properties.email();
    }

    @Override
    public void send(TestEmailMessage message, SmtpConnectionSettings connectionSettings) {
        Properties mailProperties = mailProperties(connectionSettings);

        Session session = Session.getInstance(mailProperties);
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
                            connectionSettings.password() == null ? "" : connectionSettings.password());
                } else {
                    transport.connect();
                }
                transport.sendMessage(mimeMessage, mimeMessage.getAllRecipients());
            }
        } catch (Exception exception) {
            throw new IllegalStateException(exception.getMessage(), exception);
        }
    }

    Properties mailProperties(SmtpConnectionSettings connectionSettings) {
        Properties mailProperties = new Properties();
        mailProperties.setProperty("mail.smtp.host", connectionSettings.host());
        mailProperties.setProperty("mail.smtp.port", Integer.toString(connectionSettings.port()));
        mailProperties.setProperty("mail.smtp.auth", Boolean.toString(hasText(connectionSettings.username())));
        mailProperties.setProperty(
                "mail.smtp.starttls.enable", Boolean.toString("starttls".equals(connectionSettings.securityMode())));
        mailProperties.setProperty(
                "mail.smtp.ssl.enable", Boolean.toString("ssl".equals(connectionSettings.securityMode())));
        mailProperties.setProperty(
                "mail.smtp.connectiontimeout",
                Long.toString(properties.smtpConnectionTimeout().toMillis()));
        mailProperties.setProperty(
                "mail.smtp.timeout", Long.toString(properties.smtpReadTimeout().toMillis()));
        mailProperties.setProperty(
                "mail.smtp.writetimeout",
                Long.toString(properties.smtpWriteTimeout().toMillis()));
        return mailProperties;
    }

    private boolean hasText(String value) {
        return value != null && !value.isBlank();
    }
}
