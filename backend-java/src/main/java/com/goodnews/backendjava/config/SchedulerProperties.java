package com.goodnews.backendjava.config;

import org.springframework.boot.context.properties.bind.DefaultValue;

public record SchedulerProperties(
    @DefaultValue(DEFAULT_SOURCE_SYNC_INTERVAL_MINUTES) Integer sourceSyncIntervalMinutes,
    @DefaultValue(DEFAULT_SOURCE_FAILURE_THRESHOLD) Integer sourceFailureThreshold,
    String invoker
) {
    private static final String DEFAULT_SOURCE_SYNC_INTERVAL_MINUTES = "30";
    private static final String DEFAULT_SOURCE_FAILURE_THRESHOLD = "3";
}
