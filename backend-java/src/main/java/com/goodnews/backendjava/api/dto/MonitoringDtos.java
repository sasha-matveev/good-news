package com.goodnews.backendjava.api.dto;

import java.util.Map;

public final class MonitoringDtos {

    private MonitoringDtos() {}

    public record MonitoringSummaryResponse(
        int sources_active,
        int sources_total,
        int posts_total,
        int posts_unranked,
        String last_sync_at,
        Map<String, String> services
    ) {}

    public record AnalyzeNowResponse(int analyzed, int remaining) {}

    public record MonitoringQueueItemResponse(long post_id, String title, String source_name, String created_at) {}
}
