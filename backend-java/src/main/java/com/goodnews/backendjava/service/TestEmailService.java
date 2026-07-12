package com.goodnews.backendjava.service;

import java.util.Map;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

@Service
public class TestEmailService {

    private final SettingsService settingsService;
    private final SmtpEmailAdapter smtpEmailAdapter;

    public TestEmailService(SettingsService settingsService, SmtpEmailAdapter smtpEmailAdapter) {
        this.settingsService = settingsService;
        this.smtpEmailAdapter = smtpEmailAdapter;
    }

    public Mono<Map<String, String>> sendTestEmail() {
        return settingsService
                .loadSettings()
                .flatMap(settings -> settingsService
                        .getSmtpPassword()
                        .defaultIfEmpty("")
                        .map(password -> buildCommand(settings, password)))
                .flatMap(command -> Mono.fromRunnable(
                                () -> smtpEmailAdapter.send(command.message(), command.connectionSettings()))
                        .subscribeOn(Schedulers.boundedElastic())
                        .thenReturn(Map.of("status", "sent")));
    }

    private SendTestEmailCommand buildCommand(SettingsService.AppSettings settings, String smtpPassword) {
        if (!hasText(settings.recipientEmail()) || !hasText(settings.senderIdentity())) {
            throw new IllegalStateException("Missing recipient_email or sender_identity");
        }
        return new SendTestEmailCommand(
                new SmtpEmailAdapter.TestEmailMessage(
                        settings.senderIdentity(),
                        settings.recipientEmail(),
                        "Good News digest SMTP test",
                        "<p>SMTP settings look ready.</p>"),
                new SmtpEmailAdapter.SmtpConnectionSettings(
                        defaultIfBlank(settings.smtpHost(), ""),
                        settings.smtpPort(),
                        settings.smtpUsername(),
                        smtpPassword,
                        settings.smtpSecurityMode()));
    }

    private String defaultIfBlank(String value, String defaultValue) {
        return hasText(value) ? value : defaultValue;
    }

    private boolean hasText(String value) {
        return value != null && !value.isBlank();
    }

    private record SendTestEmailCommand(
            SmtpEmailAdapter.TestEmailMessage message, SmtpEmailAdapter.SmtpConnectionSettings connectionSettings) {}
}
