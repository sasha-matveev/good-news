package com.goodnews.backendjava.config;

import org.junit.jupiter.api.Test;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.context.properties.bind.validation.BindValidationException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class GoodNewsPropertiesValidationTest {

    @Test
    void failsFastWhenNonLocalEnvironmentOmitsDatabaseAccess() {
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
            });
    }

    @Test
    void allowsPythonCompatiblePartialNonLocalConfiguration() {
        try (var context = new SpringApplicationBuilder(loadApplicationClass())
            .web(WebApplicationType.NONE)
            .properties(
                "GOOD_NEWS_ENV=prod",
                "GOOD_NEWS_DATABASE_URL=r2dbc:postgresql://db.example/good_news"
            )
            .run()) {
            assertThat(context).isNotNull();
        }
    }

    @Test
    void allowsFrontendOriginWithoutContentApiOriginWhenDatabaseIsConfigured() {
        try (var context = new SpringApplicationBuilder(loadApplicationClass())
            .web(WebApplicationType.NONE)
            .properties(
                "GOOD_NEWS_ENV=prod",
                "GOOD_NEWS_DATABASE_URL=r2dbc:postgresql://db.example/good_news",
                "GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN=https://good-news.example.com"
            )
            .run()) {
            assertThat(context).isNotNull();
        }
    }

    @Test
    void failsWhenFirebaseIsPartiallyConfigured() {
        assertValidationFailure(
            new String[] {
                "GOOD_NEWS_ENV=prod",
                "GOOD_NEWS_DATABASE_URL=r2dbc:postgresql://db.example/good_news",
                "GOOD_NEWS_FIREBASE_PROJECT_ID=demo-project"
            },
            "GOOD_NEWS_FIREBASE_PROJECT_ID is set, GOOD_NEWS_ALLOWED_EMAILS must also be set"
        );
    }

    @Test
    void failsWhenSchedulerOidcPairIsPartial() {
        assertValidationFailure(
            new String[] {
                "GOOD_NEWS_ENV=prod",
                "GOOD_NEWS_DATABASE_URL=r2dbc:postgresql://db.example/good_news",
                "GOOD_NEWS_SCHEDULER_INVOKER=scheduler@example.iam.gserviceaccount.com"
            },
            "GOOD_NEWS_SCHEDULER_INVOKER and GOOD_NEWS_OIDC_AUDIENCE"
        );
    }

    private void assertValidationFailure(String[] properties, String expectedMessageFragment) {
        assertThatThrownBy(() -> new SpringApplicationBuilder(loadApplicationClass())
            .web(WebApplicationType.NONE)
            .properties(properties)
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
}
