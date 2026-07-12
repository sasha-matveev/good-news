package com.goodnews.backendjava.api.dto;

import jakarta.validation.constraints.NotNull;

public final class PostDtos {

    private PostDtos() {}

    public record PostResponse(
            long id,
            long source_id,
            String source_name,
            String canonical_url,
            String title,
            String published_at,
            String published_at_source,
            String raw_content,
            String feedback_state,
            boolean read_later,
            String summary_ru,
            String verdict,
            String verdict_reason,
            Integer relevance_score,
            String ranking_explanation) {}

    public record ReadLaterRequest(@NotNull Boolean saved) {}

    public record ReadLaterResponse(long post_id, boolean read_later) {}

    public record OpenResponse(boolean opened) {}
}
