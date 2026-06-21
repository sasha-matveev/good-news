package com.goodnews.backendjava.config;

import org.junit.jupiter.api.Test;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;

import static org.assertj.core.api.Assertions.assertThat;

class GoodNewsPropertiesBindingTest {

    @Test
    void bindsExistingGoodNewsEnvironmentVariablesIntoLogicalGroups() {
        try (ConfigurableApplicationContext context = new SpringApplicationBuilder(loadApplicationClass())
            .web(WebApplicationType.NONE)
            .properties(
                "GOOD_NEWS_ENV=prod",
                "GOOD_NEWS_CONTENT_API_SERVICE_HOST=content-api.internal",
                "GOOD_NEWS_CONTENT_API_SERVICE_PORT=9000",
                "GOOD_NEWS_FRONTEND_PORT=4173",
                "GOOD_NEWS_ANALYSIS_SERVICE_HOST=analysis.internal",
                "GOOD_NEWS_ANALYSIS_SERVICE_PORT=9100",
                "GOOD_NEWS_SOURCE_INGESTION_SERVICE_HOST=ingestion.internal",
                "GOOD_NEWS_SOURCE_INGESTION_SERVICE_PORT=9200",
                "GOOD_NEWS_DELIVERY_SERVICE_HOST=delivery.internal",
                "GOOD_NEWS_DELIVERY_SERVICE_PORT=9300",
                "GOOD_NEWS_ANALYSIS_STUB_RESPONSE_JSON={\"mode\":\"stub\"}",
                "GOOD_NEWS_INGESTION_RESPONSES_JSON=[{\"source\":\"demo\"}]",
                "GOOD_NEWS_DATABASE_URL=r2dbc:postgresql://db.example/good_news",
                "GOOD_NEWS_POSTGRES_HOST=db.internal",
                "GOOD_NEWS_POSTGRES_PORT=6432",
                "GOOD_NEWS_POSTGRES_DATABASE=good_news_prod",
                "GOOD_NEWS_POSTGRES_USER=service_user",
                "GOOD_NEWS_POSTGRES_PASSWORD=top-secret",
                "GOOD_NEWS_FIREBASE_PROJECT_ID=demo-project",
                "GOOD_NEWS_ALLOWED_EMAILS=alice@example.com,bob@example.com",
                "GOOD_NEWS_OIDC_AUDIENCE=https://good-news.example.com",
                "GOOD_NEWS_SOURCE_SYNC_INTERVAL_MINUTES=45",
                "GOOD_NEWS_SOURCE_FAILURE_THRESHOLD=5",
                "GOOD_NEWS_SCHEDULER_INVOKER=scheduler@example.iam.gserviceaccount.com",
                "GOOD_NEWS_GEMINI_API_KEY=gemini-secret",
                "GOOD_NEWS_GEMINI_MODEL=gemini-2.5-flash-lite",
                "GOOD_NEWS_GEMINI_BATCH_SIZE=25",
                "GOOD_NEWS_GEMINI_MAX_RPM=16",
                "GOOD_NEWS_GEMINI_MAX_RETRIES=7",
                "GOOD_NEWS_APP_MASTER_KEY=master-key",
                "GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN=https://api.good-news.example.com",
                "GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN=https://good-news.example.com",
                "GOOD_NEWS_OBSERVABILITY_GRAFANA_ORIGIN=https://grafana.good-news.example.com",
                "GOOD_NEWS_OBSERVABILITY_GRAFANA_HOST=grafana.internal",
                "GOOD_NEWS_OBSERVABILITY_GRAFANA_HOST_PORT=4000",
                "GOOD_NEWS_OBSERVABILITY_DAILY_REPORT_TIME=07:15"
            )
            .run()) {
            Object properties = context.getBean(loadPropertiesClass());

            assertThat(invoke(properties, "isLocalEnvironment")).isEqualTo(false);
            assertThat(readNestedValue(properties, "getApp", "getEnvironment")).isEqualTo("prod");
            assertThat(readNestedValue(properties, "getApp", "getContentApiServiceHost")).isEqualTo("content-api.internal");
            assertThat(readNestedValue(properties, "getApp", "getContentApiServicePort")).isEqualTo(9000);
            assertThat(readNestedValue(properties, "getApp", "getFrontendPort")).isEqualTo(4173);
            assertThat(readNestedValue(properties, "getApp", "getAnalysisServiceHost")).isEqualTo("analysis.internal");
            assertThat(readNestedValue(properties, "getApp", "getAnalysisServicePort")).isEqualTo(9100);
            assertThat(readNestedValue(properties, "getApp", "getSourceIngestionServiceHost")).isEqualTo("ingestion.internal");
            assertThat(readNestedValue(properties, "getApp", "getSourceIngestionServicePort")).isEqualTo(9200);
            assertThat(readNestedValue(properties, "getApp", "getDeliveryServiceHost")).isEqualTo("delivery.internal");
            assertThat(readNestedValue(properties, "getApp", "getDeliveryServicePort")).isEqualTo(9300);
            assertThat(readNestedValue(properties, "getApp", "getAnalysisStubResponseJson")).isEqualTo("{\"mode\":\"stub\"}");
            assertThat(readNestedValue(properties, "getApp", "getIngestionResponsesJson")).isEqualTo("[{\"source\":\"demo\"}]");

            assertThat(readNestedValue(properties, "getDatabase", "getUrl")).isEqualTo("r2dbc:postgresql://db.example/good_news");
            assertThat(readNestedValue(properties, "getDatabase", "getPostgresHost")).isEqualTo("db.internal");
            assertThat(readNestedValue(properties, "getDatabase", "getPostgresPort")).isEqualTo(6432);
            assertThat(readNestedValue(properties, "getDatabase", "getPostgresDatabase")).isEqualTo("good_news_prod");
            assertThat(readNestedValue(properties, "getDatabase", "getPostgresUser")).isEqualTo("service_user");
            assertThat(readNestedValue(properties, "getDatabase", "getPostgresPassword")).isEqualTo("top-secret");

            assertThat(readNestedValue(properties, "getAuth", "getFirebaseProjectId")).isEqualTo("demo-project");
            assertThat(readNestedValue(properties, "getAuth", "getAllowedEmails")).isEqualTo("alice@example.com,bob@example.com");
            assertThat(readNestedValue(properties, "getAuth", "getOidcAudience")).isEqualTo("https://good-news.example.com");

            assertThat(readNestedValue(properties, "getScheduler", "getSourceSyncIntervalMinutes")).isEqualTo(45);
            assertThat(readNestedValue(properties, "getScheduler", "getSourceFailureThreshold")).isEqualTo(5);
            assertThat(readNestedValue(properties, "getScheduler", "getInvoker")).isEqualTo("scheduler@example.iam.gserviceaccount.com");

            assertThat(readNestedValue(properties, "getGemini", "getApiKey")).isEqualTo("gemini-secret");
            assertThat(readNestedValue(properties, "getGemini", "getModel")).isEqualTo("gemini-2.5-flash-lite");
            assertThat(readNestedValue(properties, "getGemini", "getBatchSize")).isEqualTo(25);
            assertThat(readNestedValue(properties, "getGemini", "getMaxRpm")).isEqualTo(16);
            assertThat(readNestedValue(properties, "getGemini", "getMaxRetries")).isEqualTo(7);

            assertThat(readNestedValue(properties, "getEmail", "getAppMasterKey")).isEqualTo("master-key");
            assertThat(readNestedValue(properties, "getEmail", "getPublicContentApiOrigin")).isEqualTo("https://api.good-news.example.com");
            assertThat(readNestedValue(properties, "getEmail", "getPublicFrontendOrigin")).isEqualTo("https://good-news.example.com");

            assertThat(readNestedValue(properties, "getObservability", "getGrafanaOrigin")).isEqualTo("https://grafana.good-news.example.com");
            assertThat(readNestedValue(properties, "getObservability", "getGrafanaHost")).isEqualTo("grafana.internal");
            assertThat(readNestedValue(properties, "getObservability", "getGrafanaHostPort")).isEqualTo(4000);
            assertThat(readNestedValue(properties, "getObservability", "getDailyReportTime")).isEqualTo("07:15");
        }
    }

    private Class<?> loadApplicationClass() {
        return loadClass("com.goodnews.backendjava.BackendJavaApplication");
    }

    private Class<?> loadPropertiesClass() {
        return loadClass("com.goodnews.backendjava.config.GoodNewsProperties");
    }

    private Class<?> loadClass(String className) {
        try {
            return Class.forName(className);
        } catch (ClassNotFoundException exception) {
            throw new IllegalStateException("Missing class " + className, exception);
        }
    }

    private Object readNestedValue(Object target, String firstGetter, String secondGetter) {
        return invoke(invoke(target, firstGetter), secondGetter);
    }

    private Object invoke(Object target, String methodName) {
        try {
            return target.getClass().getMethod(methodName).invoke(target);
        } catch (ReflectiveOperationException exception) {
            throw new IllegalStateException("Failed to invoke " + methodName, exception);
        }
    }
}
