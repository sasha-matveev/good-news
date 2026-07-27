package com.goodnews.backendjava.validation;

import jakarta.validation.Constraint;
import jakarta.validation.Payload;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

@Target({ElementType.FIELD, ElementType.PARAMETER, ElementType.RECORD_COMPONENT})
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = ValidFeedbackStateValidator.class)
public @interface ValidFeedbackState {

    String message() default "state must be one of interesting, not_interesting, want_to_read, norm";

    Class<?>[] groups() default {};

    Class<? extends Payload>[] payload() default {};
}
