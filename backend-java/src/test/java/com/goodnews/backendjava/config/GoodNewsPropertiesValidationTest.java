package com.goodnews.backendjava.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.context.properties.bind.validation.BindValidationException;

class GoodNewsPropertiesValidationTest {

    @Test
    void allowsDatabaseToBeUnsetWithoutLocalModeSpecialCasing() {
        try (var context = new SpringApplicationBuilder(loadApplicationClass())
                .web(WebApplicationType.NONE)
                .properties("spring.flyway.enabled=false", "GOOD_NEWS_ENV=prod")
                .run()) {
            assertThat(context).isNotNull();
        }
    }

    @Test
    void failsWhenFirebaseIsPartiallyConfigured() {
        assertValidationFailure(
                new String[] {"GOOD_NEWS_FIREBASE_PROJECT_ID=demo-project"},
                "GOOD_NEWS_FIREBASE_PROJECT_ID is set, GOOD_NEWS_ALLOWED_EMAILS must also be set");
    }

    @Test
    void failsWhenSchedulerOidcPairIsPartial() {
        assertValidationFailure(
                new String[] {"GOOD_NEWS_SCHEDULER_INVOKER=scheduler@example.iam.gserviceaccount.com"},
                "GOOD_NEWS_SCHEDULER_INVOKER and GOOD_NEWS_OIDC_AUDIENCE");
    }

    @Test
    void allowsPairedSchedulerOidcConfiguration() {
        try (var context = new SpringApplicationBuilder(loadApplicationClass())
                .web(WebApplicationType.NONE)
                .properties(
                        "spring.flyway.enabled=false",
                        "GOOD_NEWS_SCHEDULER_INVOKER=scheduler@example.iam.gserviceaccount.com",
                        "GOOD_NEWS_OIDC_AUDIENCE=https://good-news.example.com")
                .run()) {
            assertThat(context).isNotNull();
        }
    }

    private void assertValidationFailure(String[] properties, String expectedMessageFragment) {
        assertThatThrownBy(() -> new SpringApplicationBuilder(loadApplicationClass())
                        .web(WebApplicationType.NONE)
                        .properties(withFlywayDisabled(properties))
                        .run())
                .hasRootCauseInstanceOf(BindValidationException.class)
                .satisfies(exception -> {
                    Throwable rootCause = exception;
                    while (rootCause.getCause() != null) {
                        rootCause = rootCause.getCause();
                    }
                    assertThat(rootCause).isInstanceOf(BindValidationException.class);
                    assertThat(rootCause.getMessage()).contains(expectedMessageFragment);
                });
    }

    private Class<?> loadApplicationClass() {
        try {
            return Class.forName("com.goodnews.backendjava.BackendJavaApplication");
        } catch (ClassNotFoundException exception) {
            throw new IllegalStateException("Missing application class", exception);
        }
    }

    private String[] withFlywayDisabled(String[] properties) {
        String[] result = new String[properties.length + 1];
        result[0] = "spring.flyway.enabled=false";
        System.arraycopy(properties, 0, result, 1, properties.length);
        return result;
    }
}
