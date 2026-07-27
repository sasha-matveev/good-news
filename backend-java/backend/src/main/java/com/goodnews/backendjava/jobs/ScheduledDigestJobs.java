package com.goodnews.backendjava.jobs;

import com.goodnews.backendjava.digest.DigestDeliveryService;
import com.goodnews.backendjava.service.SettingsService;
import java.time.DayOfWeek;
import java.time.Instant;
import java.time.LocalTime;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.time.temporal.TemporalAdjusters;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.function.Function;
import java.util.function.Supplier;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

@Service
public final class ScheduledDigestJobs {
    private static final Logger LOGGER = LoggerFactory.getLogger(ScheduledDigestJobs.class);

    private final SettingsService settings;
    private final DigestDeliveryService delivery;
    private final String observabilityReportTime;

    public ScheduledDigestJobs(
            SettingsService settings,
            DigestDeliveryService delivery,
            com.goodnews.backendjava.config.GoodNewsProperties properties) {
        this.settings = settings;
        this.delivery = delivery;
        this.observabilityReportTime = properties.observability().dailyReportTime();
    }

    public Mono<RunResult> runDue(Instant now) {
        return Mono.defer(() -> settings.loadSettings().flatMap(appSettings -> {
            MutableResult result = new MutableResult();
            return runBranch(
                            "daily",
                            () -> runDailyIfDue(now, appSettings),
                            value -> result.dailyRanFor = value,
                            result.errors)
                    .then(runBranch(
                            "weekly",
                            () -> runWeeklyIfDue(now, appSettings),
                            value -> result.weeklyRanFor = value,
                            result.errors))
                    .then(runBranch(
                            "observability",
                            () -> runObservabilityIfDue(now),
                            value -> result.observabilityRanFor = value,
                            result.errors))
                    .then(Mono.fromSupplier(result::immutable));
        }));
    }

    private Mono<Instant> runDailyIfDue(Instant now, SettingsService.AppSettings appSettings) {
        if (!appSettings.dailyDigestEnabled() || !appSettings.dailyDigestCatchUpEnabled()) {
            return Mono.empty();
        }
        Instant due = latestDailyDue(now, appSettings.dailyDigestTime());
        return runIfNewer(due, settings::getLastDailyDigestSentAt, delivery::deliverDaily);
    }

    private Mono<Instant> runWeeklyIfDue(Instant now, SettingsService.AppSettings appSettings) {
        if (!appSettings.weeklyDigestEnabled() || !appSettings.weeklyDigestCatchUpEnabled()) {
            return Mono.empty();
        }
        Instant due = latestWeeklyDue(now, appSettings.weeklyDigestDayOfWeek(), appSettings.weeklyDigestTime());
        return runIfNewer(due, settings::getLastWeeklyDigestSentAt, delivery::deliverWeekly);
    }

    private Mono<Instant> runObservabilityIfDue(Instant now) {
        Instant due = latestDailyDue(now, observabilityReportTime);
        return runIfNewer(due, settings::getLastObservabilityReportSentAt, delivery::deliverObservabilityReport);
    }

    private Mono<Instant> runIfNewer(Instant due, Supplier<Mono<Instant>> lastSent, Function<Instant, Mono<?>> action) {
        return lastSent.get()
                .filter(previous -> !previous.isBefore(due))
                .hasElement()
                .flatMap(alreadyRan ->
                        alreadyRan ? Mono.empty() : action.apply(due).thenReturn(due));
    }

    static Instant latestDailyDue(Instant now, String scheduledTime) {
        ZonedDateTime current = now.atZone(ZoneOffset.UTC);
        LocalTime time = LocalTime.parse(scheduledTime);
        ZonedDateTime today = current.toLocalDate().atTime(time).atZone(ZoneOffset.UTC);
        return (current.isBefore(today) ? today.minusDays(1) : today).toInstant();
    }

    static Instant latestWeeklyDue(Instant now, String dayOfWeek, String scheduledTime) {
        ZonedDateTime current = now.atZone(ZoneOffset.UTC);
        DayOfWeek target = parseDay(dayOfWeek);
        LocalTime time = LocalTime.parse(scheduledTime);
        ZonedDateTime candidate = current.with(TemporalAdjusters.previousOrSame(target))
                .toLocalDate()
                .atTime(time)
                .atZone(ZoneOffset.UTC);
        return (candidate.isAfter(current) ? candidate.minusWeeks(1) : candidate).toInstant();
    }

    private static DayOfWeek parseDay(String value) {
        return switch (value.toLowerCase(Locale.ROOT)) {
            case "mon" -> DayOfWeek.MONDAY;
            case "tue" -> DayOfWeek.TUESDAY;
            case "wed" -> DayOfWeek.WEDNESDAY;
            case "thu" -> DayOfWeek.THURSDAY;
            case "fri" -> DayOfWeek.FRIDAY;
            case "sat" -> DayOfWeek.SATURDAY;
            case "sun" -> DayOfWeek.SUNDAY;
            default -> throw new IllegalArgumentException("Unsupported weekly digest day: " + value);
        };
    }

    private Mono<Void> runBranch(
            String name,
            Supplier<Mono<Instant>> branch,
            java.util.function.Consumer<Instant> success,
            List<String> errors) {
        return Mono.defer(branch).doOnNext(success).then().onErrorResume(error -> {
            String message = error.getMessage() == null ? error.getClass().getSimpleName() : error.getMessage();
            LOGGER.warn("digests job: {} failed: {}", name, message, error);
            errors.add(name + ": " + message);
            return Mono.empty();
        });
    }

    public record RunResult(
            Instant dailyRanFor, Instant weeklyRanFor, Instant observabilityRanFor, List<String> errors) {}

    private static final class MutableResult {
        private Instant dailyRanFor;
        private Instant weeklyRanFor;
        private Instant observabilityRanFor;
        private final List<String> errors = new ArrayList<>();

        private RunResult immutable() {
            return new RunResult(dailyRanFor, weeklyRanFor, observabilityRanFor, List.copyOf(errors));
        }
    }
}
