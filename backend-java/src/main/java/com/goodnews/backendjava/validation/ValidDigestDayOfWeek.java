package com.goodnews.backendjava.validation;

import jakarta.validation.Constraint;
import jakarta.validation.Payload;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

@Target({ElementType.FIELD, ElementType.PARAMETER, ElementType.RECORD_COMPONENT})
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = ValidDigestDayOfWeekValidator.class)
public @interface ValidDigestDayOfWeek {

    String message() default "weekly_digest_day_of_week must be one of mon, tue, wed, thu, fri, sat, sun";

    Class<?>[] groups() default {};

    Class<? extends Payload>[] payload() default {};
}
