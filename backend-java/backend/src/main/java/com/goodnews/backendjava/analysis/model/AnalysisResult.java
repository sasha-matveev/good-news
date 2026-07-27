package com.goodnews.backendjava.analysis.model;

import java.util.List;

public record AnalysisResult(
        long postId,
        String summaryRu,
        List<String> topics,
        String format,
        String technicalDepth,
        String verdict,
        String verdictReason,
        int relevanceScore) {}
