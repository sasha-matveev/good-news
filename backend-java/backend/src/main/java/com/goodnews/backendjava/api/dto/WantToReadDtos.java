package com.goodnews.backendjava.api.dto;

import jakarta.validation.constraints.NotNull;

public final class WantToReadDtos {

    private WantToReadDtos() {}

    public record WantToReadUpdateRequest(@NotNull Boolean saved) {}

    public record WantToReadUpdateResponse(long post_id, boolean saved, String feedback_state) {}
}
