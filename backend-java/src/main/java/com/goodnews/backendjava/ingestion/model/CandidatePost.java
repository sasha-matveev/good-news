package com.goodnews.backendjava.ingestion.model;

import java.time.Instant;

public record CandidatePost(
        String canonicalUrl,
        String title,
        Instant publishedAt,
        String rawContent,
        PublicationDateSource publicationDateSource) {}
