package com.goodnews.backendjava.config;

import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.env.EnvironmentPostProcessor;
import org.springframework.core.Ordered;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.MapPropertySource;
import org.springframework.core.env.StandardEnvironment;

public class GoodNewsEnvironmentPostProcessor implements EnvironmentPostProcessor, Ordered {

    private static final Map<String, String> ENV_TO_PROPERTY = Map.ofEntries(
            Map.entry("GOOD_NEWS_ENV", "good-news.app.environment"),
            Map.entry("GOOD_NEWS_CONTENT_API_SERVICE_HOST", "good-news.app.content-api-service-host"),
            Map.entry("GOOD_NEWS_CONTENT_API_SERVICE_PORT", "good-news.app.content-api-service-port"),
            Map.entry("GOOD_NEWS_FRONTEND_PORT", "good-news.app.frontend-port"),
            Map.entry("GOOD_NEWS_ANALYSIS_SERVICE_HOST", "good-news.app.analysis-service-host"),
            Map.entry("GOOD_NEWS_ANALYSIS_SERVICE_PORT", "good-news.app.analysis-service-port"),
            Map.entry("GOOD_NEWS_SOURCE_INGESTION_SERVICE_HOST", "good-news.app.source-ingestion-service-host"),
            Map.entry("GOOD_NEWS_SOURCE_INGESTION_SERVICE_PORT", "good-news.app.source-ingestion-service-port"),
            Map.entry("GOOD_NEWS_DELIVERY_SERVICE_HOST", "good-news.app.delivery-service-host"),
            Map.entry("GOOD_NEWS_DELIVERY_SERVICE_PORT", "good-news.app.delivery-service-port"),
            Map.entry("GOOD_NEWS_ANALYSIS_STUB_RESPONSE_JSON", "good-news.app.analysis-stub-response-json"),
            Map.entry("GOOD_NEWS_INGESTION_RESPONSES_JSON", "good-news.app.ingestion-responses-json"),
            Map.entry("GOOD_NEWS_FIXED_NOW", "good-news.app.fixed-now"),
            Map.entry("GOOD_NEWS_CONTRACT_AUTH_TOKENS_JSON", "good-news.app.contract-auth-tokens-json"),
            Map.entry("GOOD_NEWS_DATABASE_URL", "good-news.database.url"),
            Map.entry("GOOD_NEWS_POSTGRES_HOST", "good-news.database.postgres-host"),
            Map.entry("GOOD_NEWS_POSTGRES_PORT", "good-news.database.postgres-port"),
            Map.entry("GOOD_NEWS_POSTGRES_DATABASE", "good-news.database.postgres-database"),
            Map.entry("GOOD_NEWS_POSTGRES_USER", "good-news.database.postgres-user"),
            Map.entry("GOOD_NEWS_POSTGRES_PASSWORD", "good-news.database.postgres-password"),
            Map.entry("GOOD_NEWS_DATABASE_POOL_INITIAL_SIZE", "good-news.database.pool-initial-size"),
            Map.entry("GOOD_NEWS_DATABASE_POOL_MAX_SIZE", "good-news.database.pool-max-size"),
            Map.entry("GOOD_NEWS_DATABASE_POOL_ACQUIRE_TIMEOUT", "good-news.database.pool-acquire-timeout"),
            Map.entry("GOOD_NEWS_DATABASE_CONNECT_TIMEOUT", "good-news.database.connect-timeout"),
            Map.entry("GOOD_NEWS_DATABASE_OPERATION_TIMEOUT", "good-news.database.operation-timeout"),
            Map.entry("GOOD_NEWS_DATABASE_POOL_IDLE_TIMEOUT", "good-news.database.pool-idle-timeout"),
            Map.entry("GOOD_NEWS_DATABASE_POOL_MAX_LIFE_TIME", "good-news.database.pool-max-life-time"),
            Map.entry("GOOD_NEWS_FIREBASE_PROJECT_ID", "good-news.auth.firebase-project-id"),
            Map.entry("GOOD_NEWS_ALLOWED_EMAILS", "good-news.auth.allowed-emails"),
            Map.entry("GOOD_NEWS_OIDC_AUDIENCE", "good-news.auth.oidc-audience"),
            Map.entry("GOOD_NEWS_SOURCE_SYNC_INTERVAL_MINUTES", "good-news.scheduler.source-sync-interval-minutes"),
            Map.entry("GOOD_NEWS_SOURCE_FAILURE_THRESHOLD", "good-news.scheduler.source-failure-threshold"),
            Map.entry("GOOD_NEWS_SCHEDULER_INVOKER", "good-news.scheduler.invoker"),
            Map.entry("GOOD_NEWS_GEMINI_API_KEY", "good-news.gemini.api-key"),
            Map.entry("GOOD_NEWS_GEMINI_MODEL", "good-news.gemini.model"),
            Map.entry("GOOD_NEWS_GEMINI_BATCH_SIZE", "good-news.gemini.batch-size"),
            Map.entry("GOOD_NEWS_GEMINI_MAX_RPM", "good-news.gemini.max-rpm"),
            Map.entry("GOOD_NEWS_GEMINI_MAX_RETRIES", "good-news.gemini.max-retries"),
            Map.entry("GOOD_NEWS_APP_MASTER_KEY", "good-news.email.app-master-key"),
            Map.entry("GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN", "good-news.email.public-content-api-origin"),
            Map.entry("GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN", "good-news.email.public-frontend-origin"),
            Map.entry("GOOD_NEWS_SMTP_CONNECTION_TIMEOUT", "good-news.email.smtp-connection-timeout"),
            Map.entry("GOOD_NEWS_SMTP_READ_TIMEOUT", "good-news.email.smtp-read-timeout"),
            Map.entry("GOOD_NEWS_SMTP_WRITE_TIMEOUT", "good-news.email.smtp-write-timeout"),
            Map.entry("GOOD_NEWS_OBSERVABILITY_GRAFANA_ORIGIN", "good-news.observability.grafana-origin"),
            Map.entry("GOOD_NEWS_OBSERVABILITY_GRAFANA_HOST", "good-news.observability.grafana-host"),
            Map.entry("GOOD_NEWS_OBSERVABILITY_GRAFANA_HOST_PORT", "good-news.observability.grafana-host-port"),
            Map.entry("GOOD_NEWS_OBSERVABILITY_DAILY_REPORT_TIME", "good-news.observability.daily-report-time"));

    @Override
    public void postProcessEnvironment(ConfigurableEnvironment environment, SpringApplication application) {
        Map<String, Object> aliases = new LinkedHashMap<>();
        for (Map.Entry<String, String> mapping : ENV_TO_PROPERTY.entrySet()) {
            String value = environment.getProperty(mapping.getKey());
            if (value != null && !value.isBlank()) {
                aliases.put(mapping.getValue(), value);
            }
        }
        if (!aliases.isEmpty()) {
            MapPropertySource propertySource = new MapPropertySource("goodNewsEnvironmentAliases", aliases);
            if (environment
                    .getPropertySources()
                    .contains(StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME)) {
                environment
                        .getPropertySources()
                        .addAfter(StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME, propertySource);
            } else {
                environment.getPropertySources().addLast(propertySource);
            }
        }
    }

    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE;
    }
}
