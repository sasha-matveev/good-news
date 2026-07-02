package com.goodnews.backendjava.api.dto;

import jakarta.validation.constraints.NotBlank;
import java.util.List;
import java.util.Map;

public final class SourceDtos {

    private SourceDtos() {}

    public record SourceCreateRequest(@NotBlank String url) {}

    public record SourceUpdateRequest(boolean active) {}

    public record SourceResponse(
        long id,
        String display_name,
        String original_url,
        String feed_url,
        String strategy_kind,
        boolean active,
        String status,
        int post_count,
        String last_success_at,
        String last_failure_at,
        boolean needs_readaptation,
        String readaptation_reason
    ) {}

    public record SourceSyncResponse(List<Long> processed_source_ids) {}

    public record SourceLogResponse(List<Map<String, Object>> log, boolean done, String status) {}

    public record ReloadPostsResponse(int deleted, int reloaded) {}
}
