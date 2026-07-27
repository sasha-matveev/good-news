package com.goodnews.backendjava.validation;

import jakarta.validation.Constraint;
import jakarta.validation.Payload;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

@Target({ElementType.FIELD, ElementType.PARAMETER, ElementType.RECORD_COMPONENT})
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = ValidSmtpSecurityModeValidator.class)
public @interface ValidSmtpSecurityMode {

    String message() default "smtp_security_mode must be one of none, starttls, ssl";

    Class<?>[] groups() default {};

    Class<? extends Payload>[] payload() default {};
}
