package com.goodnews.backendjava.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Clock;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class ClockConfigurationTest {

    @Test
    void createsFixedClockFromContractTimestamp() {
        GoodNewsProperties properties = new GoodNewsProperties(
                new AppProperties(
                        "test",
                        "localhost",
                        8000,
                        5173,
                        "localhost",
                        8100,
                        "localhost",
                        8200,
                        "localhost",
                        8300,
                        null,
                        null,
                        "2026-04-26T12:00:00Z",
                        null),
                new DatabaseProperties(null, "localhost", 5432, "good_news", "good_news", null),
                new AuthProperties(null, "", null),
                new SchedulerProperties(30, 3, null),
                new GeminiProperties(null, "gemini-3.1-flash-lite", 10, 8, 4),
                new EmailProperties(null, null, null),
                new ObservabilityProperties(null, "127.0.0.1", 3000, "18:00"));

        Clock clock = new ClockConfiguration().clock(properties);

        assertThat(clock.instant()).isEqualTo(Instant.parse("2026-04-26T12:00:00Z"));
    }
}
