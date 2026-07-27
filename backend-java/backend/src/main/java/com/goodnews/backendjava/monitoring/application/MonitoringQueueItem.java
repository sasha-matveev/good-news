package com.goodnews.backendjava.monitoring.application;

import java.time.Instant;

public record MonitoringQueueItem(long postId, String title, String sourceName, Instant createdAt) {}
