package com.goodnews.backendjava.validation;

import jakarta.validation.ConstraintValidator;
import jakarta.validation.ConstraintValidatorContext;

public class ValidTwentyFourHourTimeValidator implements ConstraintValidator<ValidTwentyFourHourTime, String> {

    private String fieldName;

    @Override
    public void initialize(ValidTwentyFourHourTime annotation) {
        this.fieldName = annotation.fieldName();
    }

    @Override
    public boolean isValid(String value, ConstraintValidatorContext context) {
        if (value == null) {
            return true;
        }
        String[] parts = value.split(":");
        if (parts.length != 2 || !isNumeric(parts[0]) || !isNumeric(parts[1])) {
            return invalid(context);
        }
        int hour = Integer.parseInt(parts[0]);
        int minute = Integer.parseInt(parts[1]);
        return (hour >= 0 && hour < 24 && minute >= 0 && minute < 60) || invalid(context);
    }

    private boolean invalid(ConstraintValidatorContext context) {
        context.disableDefaultConstraintViolation();
        context.buildConstraintViolationWithTemplate(fieldName + " must use HH:MM format")
                .addConstraintViolation();
        return false;
    }

    private boolean isNumeric(String value) {
        return !value.isEmpty() && value.chars().allMatch(Character::isDigit);
    }
}
