package com.goodnews.backendjava.jobs;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.goodnews.backendjava.digest.DeliveryRunResult;
import com.goodnews.backendjava.digest.DigestDeliveryService;
import com.goodnews.backendjava.service.SettingsService;
import java.time.Instant;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Mono;

class ScheduledDigestJobsTest {
    private static final Instant NOW = Instant.parse("2026-07-18T13:00:00Z");

    private SettingsService settings;
    private DigestDeliveryService delivery;
    private ScheduledDigestJobs jobs;

    @BeforeEach
    void setUp() {
        settings = mock(SettingsService.class);
        delivery = mock(DigestDeliveryService.class);
        jobs = new ScheduledDigestJobs(settings, delivery);
    }

    @Test
    void dailyDueUsesTodayAfterScheduledTimeInsteadOfYesterday() {
        assertThat(ScheduledDigestJobs.latestDailyDue(NOW, "12:00")).isEqualTo(Instant.parse("2026-07-18T12:00:00Z"));
    }

    @Test
    void dailyDueUsesYesterdayBeforeScheduledTime() {
        assertThat(ScheduledDigestJobs.latestDailyDue(Instant.parse("2026-07-18T11:59:59Z"), "12:00"))
                .isEqualTo(Instant.parse("2026-07-17T12:00:00Z"));
    }

    @Test
    void weeklyDueUsesLatestConfiguredSlot() {
        assertThat(ScheduledDigestJobs.latestWeeklyDue(NOW, "sat", "12:30"))
                .isEqualTo(Instant.parse("2026-07-18T12:30:00Z"));
        assertThat(ScheduledDigestJobs.latestWeeklyDue(NOW, "sat", "14:00"))
                .isEqualTo(Instant.parse("2026-07-11T14:00:00Z"));
    }

    @Test
    void runsAllDueBranchesAndReportsTheirSlots() {
        when(settings.loadSettings()).thenReturn(Mono.just(appSettings(true, true, true, true)));
        when(settings.getLastDailyDigestSentAt()).thenReturn(Mono.empty());
        when(settings.getLastWeeklyDigestSentAt()).thenReturn(Mono.empty());
        when(delivery.deliverDaily(Instant.parse("2026-07-18T12:00:00Z"))).thenReturn(Mono.just(result()));
        when(delivery.deliverWeekly(Instant.parse("2026-07-12T23:30:00Z"))).thenReturn(Mono.just(result()));

        ScheduledDigestJobs.RunResult result = jobs.runDue(NOW).block();

        assertThat(result.dailyRanFor()).isEqualTo(Instant.parse("2026-07-18T12:00:00Z"));
        assertThat(result.weeklyRanFor()).isEqualTo(Instant.parse("2026-07-12T23:30:00Z"));
        assertThat(result.errors()).isEmpty();
    }

    @Test
    void skipsDisabledAndAlreadyCompletedBranches() {
        when(settings.loadSettings()).thenReturn(Mono.just(appSettings(false, true, true, true)));
        when(settings.getLastWeeklyDigestSentAt()).thenReturn(Mono.just(Instant.parse("2026-07-12T23:30:00Z")));

        ScheduledDigestJobs.RunResult result = jobs.runDue(NOW).block();

        assertThat(result.dailyRanFor()).isNull();
        assertThat(result.weeklyRanFor()).isNull();
        assertThat(result.errors()).isEmpty();
        verifyNoInteractions(delivery);
    }

    @Test
    void oneBranchFailureDoesNotPreventLaterBranches() {
        when(settings.loadSettings()).thenReturn(Mono.just(appSettings(true, true, true, true)));
        when(settings.getLastDailyDigestSentAt()).thenReturn(Mono.empty());
        when(settings.getLastWeeklyDigestSentAt()).thenReturn(Mono.empty());
        Instant dailyDue = Instant.parse("2026-07-18T12:00:00Z");
        Instant weeklyDue = Instant.parse("2026-07-12T23:30:00Z");
        when(delivery.deliverDaily(dailyDue)).thenReturn(Mono.error(new IllegalStateException("SMTP down")));
        when(delivery.deliverWeekly(weeklyDue)).thenReturn(Mono.just(result()));

        ScheduledDigestJobs.RunResult result = jobs.runDue(NOW).block();

        assertThat(result.dailyRanFor()).isNull();
        assertThat(result.weeklyRanFor()).isEqualTo(weeklyDue);
        assertThat(result.errors()).containsExactly("daily: SMTP down");
    }

    private SettingsService.AppSettings appSettings(
            boolean dailyEnabled, boolean dailyCatchUp, boolean weeklyEnabled, boolean weeklyCatchUp) {
        return new SettingsService.AppSettings(
                "12:00",
                "sun",
                "23:30",
                null,
                null,
                null,
                587,
                null,
                "starttls",
                dailyEnabled,
                dailyCatchUp,
                weeklyEnabled,
                weeklyCatchUp,
                false,
                "summary",
                "verdict");
    }

    private DeliveryRunResult result() {
        return new DeliveryRunResult(1, "skipped", false, 0);
    }
}
