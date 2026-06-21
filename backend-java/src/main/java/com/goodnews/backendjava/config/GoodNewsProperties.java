package com.goodnews.backendjava.config;

import jakarta.validation.Valid;
import jakarta.validation.constraints.AssertTrue;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

import java.util.Locale;
import java.util.Set;

@Validated
@ConfigurationProperties(prefix = "good-news")
public class GoodNewsProperties {

    private static final Set<String> LOCAL_ENVIRONMENTS = Set.of("local", "dev", "test");

    @Valid
    private final AppProperties app = new AppProperties();

    @Valid
    private final DatabaseProperties database = new DatabaseProperties();

    @Valid
    private final AuthProperties auth = new AuthProperties();

    @Valid
    private final SchedulerProperties scheduler = new SchedulerProperties();

    @Valid
    private final GeminiProperties gemini = new GeminiProperties();

    @Valid
    private final EmailProperties email = new EmailProperties();

    @Valid
    private final ObservabilityProperties observability = new ObservabilityProperties();

    public AppProperties getApp() {
        return app;
    }

    public DatabaseProperties getDatabase() {
        return database;
    }

    public AuthProperties getAuth() {
        return auth;
    }

    public SchedulerProperties getScheduler() {
        return scheduler;
    }

    public GeminiProperties getGemini() {
        return gemini;
    }

    public EmailProperties getEmail() {
        return email;
    }

    public ObservabilityProperties getObservability() {
        return observability;
    }

    public boolean isLocalEnvironment() {
        String environment = app.getEnvironment();
        if (environment == null) {
            return true;
        }
        return LOCAL_ENVIRONMENTS.contains(environment.trim().toLowerCase(Locale.ROOT));
    }

    @AssertTrue(message = "Non-local environments must set GOOD_NEWS_DATABASE_URL or GOOD_NEWS_POSTGRES_PASSWORD.")
    public boolean isDatabaseConfigured() {
        return isLocalEnvironment() || hasText(database.getUrl()) || hasText(database.getPostgresPassword());
    }

    @AssertTrue(message = "When GOOD_NEWS_FIREBASE_PROJECT_ID is set, GOOD_NEWS_ALLOWED_EMAILS must also be set.")
    public boolean isFirebaseAuthConfigured() {
        return !hasText(auth.getFirebaseProjectId()) || hasText(auth.getAllowedEmails());
    }

    @AssertTrue(message = "Set both GOOD_NEWS_SCHEDULER_INVOKER and GOOD_NEWS_OIDC_AUDIENCE, or leave both unset.")
    public boolean isSchedulerOidcConfigured() {
        return hasText(scheduler.getInvoker()) == hasText(auth.getOidcAudience());
    }

    private boolean hasText(String value) {
        return value != null && !value.isBlank();
    }
}
