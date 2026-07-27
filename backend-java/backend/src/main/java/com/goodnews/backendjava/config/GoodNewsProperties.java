package com.goodnews.backendjava.config;

import jakarta.validation.Valid;
import jakarta.validation.constraints.AssertTrue;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties(prefix = "good-news")
public record GoodNewsProperties(
        @Valid @DefaultValue AppProperties app,
        @Valid @DefaultValue DatabaseProperties database,
        @Valid @DefaultValue AuthProperties auth,
        @Valid @DefaultValue SchedulerProperties scheduler,
        @Valid @DefaultValue GeminiProperties gemini,
        @Valid @DefaultValue EmailProperties email,
        @Valid @DefaultValue ObservabilityProperties observability) {

    @AssertTrue(message = "When GOOD_NEWS_FIREBASE_PROJECT_ID is set, GOOD_NEWS_ALLOWED_EMAILS must also be set.")
    public boolean isFirebaseAuthConfigured() {
        return !hasText(auth.firebaseProjectId()) || hasText(auth.allowedEmails());
    }

    @AssertTrue(message = "Set both GOOD_NEWS_SCHEDULER_INVOKER and GOOD_NEWS_OIDC_AUDIENCE, or leave both unset.")
    public boolean isSchedulerOidcConfigured() {
        return hasText(scheduler.invoker()) == hasText(auth.oidcAudience());
    }

    private boolean hasText(String value) {
        return value != null && !value.isBlank();
    }
}
