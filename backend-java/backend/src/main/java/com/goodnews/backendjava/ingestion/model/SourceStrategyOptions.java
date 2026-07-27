package com.goodnews.backendjava.ingestion.model;

public record SourceStrategyOptions(String listingUrl, String linkSelector, String siteKey) {
    public static SourceStrategyOptions empty() {
        return new SourceStrategyOptions(null, null, null);
    }
}
