package com.goodnews.backendjava.ingestion.application;

public final class SourceNotFoundException extends RuntimeException {
    private final long sourceId;

    public SourceNotFoundException(long sourceId) {
        super("Source not found");
        this.sourceId = sourceId;
    }

    public long sourceId() {
        return sourceId;
    }
}
