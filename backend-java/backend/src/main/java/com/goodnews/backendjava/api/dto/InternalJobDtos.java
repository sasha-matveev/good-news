package com.goodnews.backendjava.api.dto;

import java.util.List;

public final class InternalJobDtos {

    private InternalJobDtos() {}

    public record SourceSyncJobResponse(List<Long> processed_source_ids, boolean analyzed_pending) {}

    public record DigestJobResponse(
            String daily_ran_for, String weekly_ran_for, String observability_ran_for, List<String> errors) {}
}
