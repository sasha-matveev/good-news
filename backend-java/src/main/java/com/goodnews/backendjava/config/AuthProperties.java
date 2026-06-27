package com.goodnews.backendjava.config;

import org.springframework.boot.context.properties.bind.DefaultValue;

public record AuthProperties(
    String firebaseProjectId,
    @DefaultValue(DEFAULT_ALLOWED_EMAILS) String allowedEmails,
    String oidcAudience
) {
    private static final String DEFAULT_ALLOWED_EMAILS = "";
}
