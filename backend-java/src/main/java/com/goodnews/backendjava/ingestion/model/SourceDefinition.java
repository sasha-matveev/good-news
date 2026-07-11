package com.goodnews.backendjava.ingestion.model;

import java.time.Instant;

public record SourceDefinition(
        long id,
        String originalUrl,
        String feedUrl,
        SourceStrategyKind strategyKind,
        SourceStrategyOptions options,
        Instant lastSuccessAt) {}
