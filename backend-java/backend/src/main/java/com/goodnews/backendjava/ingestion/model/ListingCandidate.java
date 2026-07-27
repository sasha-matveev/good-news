package com.goodnews.backendjava.ingestion.model;

import java.time.Instant;

public record ListingCandidate(
        String href,
        String title,
        Instant publishedAt,
        PublicationDateSource publicationDateSource,
        String rawContent) {}
