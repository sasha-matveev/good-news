package com.goodnews.backendjava.ingestion.model;

public enum SourceStrategyKind {
    FEED("feed"),
    HTML("html"),
    KNOWN_SITE("known_site");

    private final String persistedValue;

    SourceStrategyKind(String persistedValue) {
        this.persistedValue = persistedValue;
    }

    public String persistedValue() {
        return persistedValue;
    }

    public static SourceStrategyKind fromPersistedValue(String value) {
        for (SourceStrategyKind kind : values()) {
            if (kind.persistedValue.equals(value)) {
                return kind;
            }
        }
        throw new IllegalArgumentException("Unsupported source strategy " + value);
    }
}
