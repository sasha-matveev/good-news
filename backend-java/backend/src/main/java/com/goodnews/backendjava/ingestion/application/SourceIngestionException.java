package com.goodnews.backendjava.ingestion.application;

public final class SourceIngestionException extends RuntimeException {
    public SourceIngestionException(String message) {
        super(message);
    }

    public SourceIngestionException(String message, Throwable cause) {
        super(message, cause);
    }
}
