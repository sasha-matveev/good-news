package com.goodnews.backendjava.validation;

import jakarta.validation.ConstraintValidator;
import jakarta.validation.ConstraintValidatorContext;
import java.util.Set;

public class ValidSmtpSecurityModeValidator implements ConstraintValidator<ValidSmtpSecurityMode, String> {

    private static final Set<String> VALID_VALUES = Set.of("none", "starttls", "ssl");

    @Override
    public boolean isValid(String value, ConstraintValidatorContext context) {
        if (value == null) {
            return true;
        }
        return VALID_VALUES.contains(value);
    }
}
