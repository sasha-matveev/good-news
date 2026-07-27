package com.goodnews.backendjava.api.dto;

import com.goodnews.backendjava.validation.ValidFeedbackState;
import jakarta.validation.constraints.NotNull;

public final class FeedbackDtos {

    private FeedbackDtos() {}

    public record FeedbackUpdateRequest(@NotNull @ValidFeedbackState String state) {}

    public record FeedbackResponse(long post_id, String state) {}
}
