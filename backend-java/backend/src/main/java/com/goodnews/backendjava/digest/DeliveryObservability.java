package com.goodnews.backendjava.digest;

import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
public final class DeliveryObservability {
    private static final Logger LOGGER = LoggerFactory.getLogger(DeliveryObservability.class);

    private final MeterRegistry meters;

    public DeliveryObservability(MeterRegistry meters) {
        this.meters = meters;
    }

    public void record(DigestType type, String status) {
        meters.counter("good.news.delivery.runs", "digest_type", type.databaseValue(), "status", status)
                .increment();
        if ("failed".equals(status) || "indeterminate".equals(status)) {
            LOGGER.warn("event=delivery_run digest_type={} status={}", type.databaseValue(), status);
        } else {
            LOGGER.info("event=delivery_run digest_type={} status={}", type.databaseValue(), status);
        }
    }
}
