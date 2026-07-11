package com.goodnews.backendjava.ingestion.application;

import java.util.List;

public record SyncOutcome(List<Long> processedSourceIds) {
    public static SyncOutcome success(long sourceId) {
        return new SyncOutcome(List.of(sourceId));
    }

    public static SyncOutcome failure() {
        return new SyncOutcome(List.of());
    }
}
