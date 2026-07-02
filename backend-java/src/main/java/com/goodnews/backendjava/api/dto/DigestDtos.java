package com.goodnews.backendjava.api.dto;

import java.util.List;

public final class DigestDtos {

    private DigestDtos() {}

    public record DigestListItemResponse(
        long id,
        String digest_type,
        String status,
        String sent_at,
        int included_post_count
    ) {}

    public record DigestIncludedPostResponse(
        long post_id,
        String title,
        String feedback_state
    ) {}

    public record DigestDetailResponse(
        long id,
        String digest_type,
        String status,
        String sent_at,
        String title,
        List<DigestIncludedPostResponse> included_posts,
        String rendered_html
    ) {}
}
