package com.goodnews.backendjava.validation;

import jakarta.validation.ConstraintValidator;
import jakarta.validation.ConstraintValidatorContext;
import java.util.Set;

public class ValidDigestDayOfWeekValidator implements ConstraintValidator<ValidDigestDayOfWeek, String> {

    private static final Set<String> VALID_VALUES = Set.of("mon", "tue", "wed", "thu", "fri", "sat", "sun");

    @Override
    public boolean isValid(String value, ConstraintValidatorContext context) {
        if (value == null) {
            return true;
        }
        return VALID_VALUES.contains(value.trim().toLowerCase());
    }
}
