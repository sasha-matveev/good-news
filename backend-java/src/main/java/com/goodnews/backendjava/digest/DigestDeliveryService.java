package com.goodnews.backendjava.digest;

import com.goodnews.backendjava.service.SettingsService;
import com.goodnews.backendjava.service.SmtpEmailAdapter;
import java.time.Instant;
import org.springframework.stereotype.Service;
import org.springframework.transaction.reactive.TransactionalOperator;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

@Service
public final class DigestDeliveryService {
    private final DigestGenerationService generator;
    private final DigestRepository digests;
    private final SettingsService settings;
    private final SmtpEmailAdapter smtp;
    private final TransactionalOperator transactions;
    private final DeliveryObservability observability;

    public DigestDeliveryService(
            DigestGenerationService generator,
            DigestRepository digests,
            SettingsService settings,
            SmtpEmailAdapter smtp,
            TransactionalOperator transactions,
            DeliveryObservability observability) {
        this.generator = generator;
        this.digests = digests;
        this.settings = settings;
        this.smtp = smtp;
        this.transactions = transactions;
        this.observability = observability;
    }

    public Mono<DeliveryRunResult> deliverDaily(Instant now) {
        return deliver(DigestType.DAILY, now);
    }

    public Mono<DeliveryRunResult> deliverWeekly(Instant now) {
        return deliver(DigestType.WEEKLY, now);
    }

    private Mono<DeliveryRunResult> deliver(DigestType type, Instant now) {
        Mono<GeneratedDigest> generated =
                type == DigestType.DAILY ? generator.generateDaily(now) : generator.generateWeekly(now);
        return guardNoPriorRun(type, now)
                .then(generated)
                .flatMap(digest -> deliveryDecision(digest)
                        .onErrorResume(error -> error instanceof SmtpDeliveryException
                                ? markIndeterminateThenError(digest.digestId(), (SmtpDeliveryException) error)
                                : digests.markFailed(digest.digestId()).then(Mono.error(error)))
                        .flatMap(decision -> finalizeDelivery(digest, decision, now)))
                .doOnError(error -> observability.record(type, outcomeStatus(error)));
    }

    private Mono<Void> guardNoPriorRun(DigestType type, Instant now) {
        return digests.findRunStatus(type, now)
                .flatMap(status -> "failed".equals(status)
                        ? Mono.empty()
                        : Mono.error(new ExistingDigestRunException(type, now, status)))
                .then();
    }

    private Mono<DeliveryDecision> deliveryDecision(GeneratedDigest digest) {
        return settings.loadSettings().flatMap(appSettings -> {
            if (!hasText(appSettings.recipientEmail()) || !hasText(appSettings.senderIdentity())) {
                return Mono.just(new DeliveryDecision(true, null));
            }
            return settings.getSmtpPassword()
                    .defaultIfEmpty("")
                    .map(password -> command(digest, appSettings, password))
                    .flatMap(command ->
                            send(command).thenReturn(new DeliveryDecision(false, appSettings.recipientEmail())));
        });
    }

    private Mono<DeliveryRunResult> finalizeDelivery(GeneratedDigest digest, DeliveryDecision decision, Instant now) {
        if (decision.skipped()) {
            Mono<Void> skipped = digests.markSkipped(digest.digestId()).then(setLastSentAt(digest.type(), now));
            return skipped.as(transactions::transactional)
                    .doOnSuccess(ignored -> observability.record(digest.type(), "skipped"))
                    .thenReturn(new DeliveryRunResult(digest.digestId(), "skipped", false, digest.itemCount()));
        }
        return markSent(digest, decision.recipient(), now)
                .onErrorResume(
                        error -> markIndeterminateThenError(digest.digestId(), new PostSendPersistenceException(error)))
                .doOnSuccess(ignored -> observability.record(digest.type(), "sent"))
                .thenReturn(new DeliveryRunResult(digest.digestId(), "sent", true, digest.itemCount()));
    }

    private Mono<Void> send(SendCommand command) {
        return Mono.fromRunnable(() -> smtp.send(command.message(), command.connectionSettings()))
                .subscribeOn(Schedulers.boundedElastic())
                .onErrorMap(SmtpDeliveryException::new)
                .then();
    }

    private String outcomeStatus(Throwable error) {
        if (error instanceof PostSendPersistenceException
                || error instanceof SmtpDeliveryException
                || error instanceof IndeterminateStatePersistenceException) {
            return "indeterminate";
        }
        if (error instanceof ExistingDigestRunException existing) {
            return existing.isUncertain() ? "indeterminate" : "duplicate_blocked";
        }
        if (error instanceof DigestRepository.DigestRunConflictException) {
            return "duplicate_blocked";
        }
        return "failed";
    }

    private Mono<Void> markSent(GeneratedDigest digest, String recipient, Instant now) {
        return digests.markSent(digest.digestId(), recipient, now)
                .then(setLastSentAt(digest.type(), now))
                .as(transactions::transactional);
    }

    private <T> Mono<T> markIndeterminateThenError(long digestId, RuntimeException original) {
        return digests.markIndeterminate(digestId)
                .onErrorMap(persistenceError -> new IndeterminateStatePersistenceException(original, persistenceError))
                .then(Mono.error(original));
    }

    private Mono<Void> setLastSentAt(DigestType type, Instant now) {
        return type == DigestType.DAILY
                ? settings.setLastDailyDigestSentAt(now)
                : settings.setLastWeeklyDigestSentAt(now);
    }

    private SendCommand command(GeneratedDigest digest, SettingsService.AppSettings appSettings, String smtpPassword) {
        return new SendCommand(
                new SmtpEmailAdapter.TestEmailMessage(
                        appSettings.senderIdentity(),
                        appSettings.recipientEmail(),
                        digest.subject(),
                        digest.htmlBody()),
                new SmtpEmailAdapter.SmtpConnectionSettings(
                        defaultIfBlank(appSettings.smtpHost(), ""),
                        appSettings.smtpPort(),
                        appSettings.smtpUsername(),
                        smtpPassword,
                        appSettings.smtpSecurityMode()));
    }

    private String defaultIfBlank(String value, String defaultValue) {
        return hasText(value) ? value : defaultValue;
    }

    private boolean hasText(String value) {
        return value != null && !value.isBlank();
    }

    private record SendCommand(
            SmtpEmailAdapter.TestEmailMessage message, SmtpEmailAdapter.SmtpConnectionSettings connectionSettings) {}

    private record DeliveryDecision(boolean skipped, String recipient) {}

    private static final class PostSendPersistenceException extends RuntimeException {
        private PostSendPersistenceException(Throwable cause) {
            super("SMTP accepted the message, but delivery state could not be persisted", cause);
        }
    }

    private static final class SmtpDeliveryException extends RuntimeException {
        private SmtpDeliveryException(Throwable cause) {
            super("SMTP delivery outcome is indeterminate", cause);
        }
    }

    private static final class IndeterminateStatePersistenceException extends RuntimeException {
        private IndeterminateStatePersistenceException(RuntimeException original, Throwable persistenceError) {
            super("Delivery outcome is indeterminate and could not be persisted", original);
            addSuppressed(persistenceError);
        }
    }

    private static final class ExistingDigestRunException extends RuntimeException {
        private final String status;

        private ExistingDigestRunException(DigestType type, Instant scheduledFor, String status) {
            super("Digest run already exists for " + type.databaseValue() + " at " + scheduledFor + " with status "
                    + status);
            this.status = status;
        }

        private boolean isUncertain() {
            return "generated".equals(status) || "indeterminate".equals(status);
        }
    }
}
