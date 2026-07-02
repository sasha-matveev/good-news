package com.goodnews.backendjava.validation;

import jakarta.validation.ConstraintValidator;
import jakarta.validation.ConstraintValidatorContext;
import java.util.Set;

public class ValidFeedbackStateValidator implements ConstraintValidator<ValidFeedbackState, String> {

    private static final Set<String> VALID_VALUES = Set.of("interesting", "not_interesting", "want_to_read", "norm");

    @Override
    public boolean isValid(String value, ConstraintValidatorContext context) {
        if (value == null) {
            return true;
        }
        return VALID_VALUES.contains(value);
    }
}
