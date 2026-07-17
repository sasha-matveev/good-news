package com.goodnews.backendjava.digest;

public record DigestEmailPost(
        long postId,
        String title,
        String sourceName,
        String canonicalUrl,
        String summaryRu,
        String verdict,
        String verdictReason,
        Integer relevanceScore) {}
