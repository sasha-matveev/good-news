package com.goodnews.backendjava.digest;

import static org.assertj.core.api.Assertions.assertThat;

import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;

class DeliveryObservabilityTest {

    @Test
    void recordsDeliveryRunsByTypeAndStatus() {
        SimpleMeterRegistry meters = new SimpleMeterRegistry();
        DeliveryObservability observability = new DeliveryObservability(meters);

        observability.record(DigestType.DAILY, "sent");
        observability.record(DigestType.DAILY, "sent");
        observability.record(DigestType.WEEKLY, "failed");

        assertThat(meters.get("good.news.delivery.runs")
                        .tags("digest_type", "daily", "status", "sent")
                        .counter()
                        .count())
                .isEqualTo(2.0);
        assertThat(meters.get("good.news.delivery.runs")
                        .tags("digest_type", "weekly", "status", "failed")
                        .counter()
                        .count())
                .isEqualTo(1.0);
    }
}
