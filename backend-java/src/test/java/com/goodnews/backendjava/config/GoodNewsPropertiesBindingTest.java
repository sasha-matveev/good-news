package com.goodnews.backendjava.config;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.util.TestPropertyValues;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.Configuration;

class GoodNewsPropertiesBindingTest {

    @Test
    void bindsRemainingGoodNewsEnvironmentVariablesIntoRecords() {
        try (ConfigurableApplicationContext context = new SpringApplicationBuilder(TestConfiguration.class)
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
                        "GOOD_NEWS_DATABASE_POOL_INITIAL_SIZE=1",
                        "GOOD_NEWS_DATABASE_POOL_MAX_SIZE=4",
                        "GOOD_NEWS_DATABASE_POOL_ACQUIRE_TIMEOUT=750ms",
                        "GOOD_NEWS_DATABASE_CONNECT_TIMEOUT=3s",
                        "GOOD_NEWS_DATABASE_OPERATION_TIMEOUT=12s",
                        "GOOD_NEWS_DATABASE_POOL_IDLE_TIMEOUT=5m",
                        "GOOD_NEWS_DATABASE_POOL_MAX_LIFE_TIME=20m",
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
                        "GOOD_NEWS_SMTP_CONNECTION_TIMEOUT=4s",
                        "GOOD_NEWS_SMTP_READ_TIMEOUT=14s",
                        "GOOD_NEWS_SMTP_WRITE_TIMEOUT=15s",
                        "GOOD_NEWS_OBSERVABILITY_GRAFANA_ORIGIN=https://grafana.good-news.example.com",
                        "GOOD_NEWS_OBSERVABILITY_GRAFANA_HOST=grafana.internal",
                        "GOOD_NEWS_OBSERVABILITY_GRAFANA_HOST_PORT=3300",
                        "GOOD_NEWS_OBSERVABILITY_DAILY_REPORT_TIME=19:15")
                .run()) {
            GoodNewsProperties properties = context.getBean(GoodNewsProperties.class);

            assertThat(properties.app().environment()).isEqualTo("prod");
            assertThat(properties.app().contentApiServiceHost()).isEqualTo("content-api.internal");
            assertThat(properties.app().contentApiServicePort()).isEqualTo(9000);
            assertThat(properties.app().frontendPort()).isEqualTo(4173);
            assertThat(properties.app().analysisServiceHost()).isEqualTo("analysis.internal");
            assertThat(properties.app().analysisServicePort()).isEqualTo(9100);
            assertThat(properties.app().sourceIngestionServiceHost()).isEqualTo("ingestion.internal");
            assertThat(properties.app().sourceIngestionServicePort()).isEqualTo(9200);
            assertThat(properties.app().deliveryServiceHost()).isEqualTo("delivery.internal");
            assertThat(properties.app().deliveryServicePort()).isEqualTo(9300);
            assertThat(properties.app().analysisStubResponseJson()).isEqualTo("{\"mode\":\"stub\"}");
            assertThat(properties.app().ingestionResponsesJson()).isEqualTo("[{\"source\":\"demo\"}]");

            assertThat(properties.database().url()).isEqualTo("r2dbc:postgresql://db.example/good_news");
            assertThat(properties.database().postgresHost()).isEqualTo("db.internal");
            assertThat(properties.database().postgresPort()).isEqualTo(6432);
            assertThat(properties.database().postgresDatabase()).isEqualTo("good_news_prod");
            assertThat(properties.database().postgresUser()).isEqualTo("service_user");
            assertThat(properties.database().postgresPassword()).isEqualTo("top-secret");
            assertThat(properties.database().poolInitialSize()).isEqualTo(1);
            assertThat(properties.database().poolMaxSize()).isEqualTo(4);
            assertThat(properties.database().poolAcquireTimeout()).isEqualTo(java.time.Duration.ofMillis(750));
            assertThat(properties.database().connectTimeout()).isEqualTo(java.time.Duration.ofSeconds(3));
            assertThat(properties.database().operationTimeout()).isEqualTo(java.time.Duration.ofSeconds(12));
            assertThat(properties.database().poolIdleTimeout()).isEqualTo(java.time.Duration.ofMinutes(5));
            assertThat(properties.database().poolMaxLifeTime()).isEqualTo(java.time.Duration.ofMinutes(20));

            assertThat(properties.auth().firebaseProjectId()).isEqualTo("demo-project");
            assertThat(properties.auth().allowedEmails()).isEqualTo("alice@example.com,bob@example.com");
            assertThat(properties.auth().oidcAudience()).isEqualTo("https://good-news.example.com");

            assertThat(properties.scheduler().sourceSyncIntervalMinutes()).isEqualTo(45);
            assertThat(properties.scheduler().sourceFailureThreshold()).isEqualTo(5);
            assertThat(properties.scheduler().invoker()).isEqualTo("scheduler@example.iam.gserviceaccount.com");

            assertThat(properties.gemini().apiKey()).isEqualTo("gemini-secret");
            assertThat(properties.gemini().model()).isEqualTo("gemini-2.5-flash-lite");
            assertThat(properties.gemini().batchSize()).isEqualTo(25);
            assertThat(properties.gemini().maxRpm()).isEqualTo(16);
            assertThat(properties.gemini().maxRetries()).isEqualTo(7);

            assertThat(properties.email().appMasterKey()).isEqualTo("master-key");
            assertThat(properties.email().publicContentApiOrigin()).isEqualTo("https://api.good-news.example.com");
            assertThat(properties.email().publicFrontendOrigin()).isEqualTo("https://good-news.example.com");
            assertThat(properties.email().smtpConnectionTimeout()).isEqualTo(java.time.Duration.ofSeconds(4));
            assertThat(properties.email().smtpReadTimeout()).isEqualTo(java.time.Duration.ofSeconds(14));
            assertThat(properties.email().smtpWriteTimeout()).isEqualTo(java.time.Duration.ofSeconds(15));
            assertThat(properties.observability().grafanaOrigin()).isEqualTo("https://grafana.good-news.example.com");
            assertThat(properties.observability().grafanaHost()).isEqualTo("grafana.internal");
            assertThat(properties.observability().grafanaHostPort()).isEqualTo(3300);
            assertThat(properties.observability().dailyReportTime()).isEqualTo("19:15");
        }
    }

    @Test
    void explicitGoodNewsPropertiesOverrideLegacyGoodNewsEnvironmentAliases() {
        try (ConfigurableApplicationContext context = new SpringApplicationBuilder(TestConfiguration.class)
                .web(WebApplicationType.NONE)
                .properties("GOOD_NEWS_ENV=prod", "GOOD_NEWS_GEMINI_MODEL=gemini-2.5-flash-lite")
                .initializers(applicationContext -> TestPropertyValues.of(
                                "good-news.app.environment=test", "good-news.gemini.model=gemini-explicit")
                        .applyTo(applicationContext))
                .run()) {
            GoodNewsProperties properties = context.getBean(GoodNewsProperties.class);

            assertThat(properties.app().environment()).isEqualTo("test");
            assertThat(properties.gemini().model()).isEqualTo("gemini-explicit");
        }
    }

    @Configuration(proxyBeanMethods = false)
    @EnableConfigurationProperties(GoodNewsProperties.class)
    static class TestConfiguration {}
}
