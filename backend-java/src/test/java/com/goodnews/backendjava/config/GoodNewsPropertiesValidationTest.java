package com.goodnews.backendjava.config;

import org.junit.jupiter.api.Test;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.context.properties.bind.validation.BindValidationException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class GoodNewsPropertiesValidationTest {

    @Test
    void failsFastWhenNonLocalEnvironmentOmitsRequiredValues() {
        assertThatThrownBy(() -> new SpringApplicationBuilder(loadApplicationClass())
            .web(WebApplicationType.NONE)
            .properties("GOOD_NEWS_ENV=prod")
            .run())
            .hasRootCauseInstanceOf(BindValidationException.class)
            .satisfies(exception -> {
                Throwable rootCause = exception;
                while (rootCause.getCause() != null) {
                    rootCause = rootCause.getCause();
                }
                assertThat(rootCause).isInstanceOf(BindValidationException.class);
                assertThat(rootCause.getMessage()).contains("GOOD_NEWS_DATABASE_URL or GOOD_NEWS_POSTGRES_PASSWORD");
                assertThat(rootCause.getMessage()).contains("GOOD_NEWS_APP_MASTER_KEY");
                assertThat(rootCause.getMessage()).contains("GOOD_NEWS_GEMINI_API_KEY");
                assertThat(rootCause.getMessage()).contains("GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN and GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN");
                assertThat(rootCause.getMessage()).contains("GOOD_NEWS_FIREBASE_PROJECT_ID, GOOD_NEWS_ALLOWED_EMAILS, GOOD_NEWS_SCHEDULER_INVOKER, and GOOD_NEWS_OIDC_AUDIENCE");
            });
    }

    private Class<?> loadApplicationClass() {
        try {
            return Class.forName("com.goodnews.backendjava.BackendJavaApplication");
        } catch (ClassNotFoundException exception) {
            throw new IllegalStateException("Missing application class", exception);
        }
    }
}
