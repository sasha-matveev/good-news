package com.goodnews.backendjava.api.contract;

import com.fasterxml.jackson.annotation.JsonInclude;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import org.springframework.validation.FieldError;

@JsonInclude(JsonInclude.Include.NON_NULL)
record ApiValidationError(List<String> loc, String msg, String type, Object input, Map<String, Object> ctx) {

    private static final String FEEDBACK_STATE_CONSTRAINT = "ValidFeedbackState";
    private static final String FEEDBACK_STATE_EXPECTED = "'interesting', 'not_interesting', 'want_to_read' or 'norm'";

    static ApiValidationError from(FieldError error) {
        if (FEEDBACK_STATE_CONSTRAINT.equals(error.getCode())) {
            return new ApiValidationError(
                    List.of("body", error.getField()),
                    "Input should be " + FEEDBACK_STATE_EXPECTED,
                    "literal_error",
                    error.getRejectedValue(),
                    Map.of("expected", FEEDBACK_STATE_EXPECTED));
        }
        return valueError(
                "body",
                error.getField(),
                Objects.requireNonNullElse(error.getDefaultMessage(), "Validation failed"),
                null);
    }

    static ApiValidationError valueError(String location, String field, String message, Object rejectedValue) {
        return new ApiValidationError(List.of(location, field), message, "value_error", rejectedValue, null);
    }
}
