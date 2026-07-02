package com.goodnews.backendjava.api.dto;

import java.util.List;

public final class PreferenceDtos {

    private PreferenceDtos() {}

    public record PreferenceFeedbackTotalsResponse(
        int total,
        int interesting,
        int want_to_read,
        int not_interesting
    ) {}

    public record PreferenceProfileResponse(
        String summary,
        List<String> positive_signals,
        List<String> negative_signals,
        List<String> learning_proof,
        PreferenceFeedbackTotalsResponse feedback_totals
    ) {}
}
