package com.goodnews.backendjava.monitoring.application;

import java.time.Instant;
import java.util.Map;

public record MonitoringSummary(
        int sourcesActive,
        int sourcesTotal,
        int postsTotal,
        int postsUnranked,
        Instant lastSyncAt,
        Map<String, String> services) {}
