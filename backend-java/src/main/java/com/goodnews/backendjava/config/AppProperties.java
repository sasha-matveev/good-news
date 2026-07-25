package com.goodnews.backendjava.config;

import org.springframework.boot.context.properties.bind.DefaultValue;

public record AppProperties(
        @DefaultValue(DEFAULT_ENVIRONMENT) String environment,
        @DefaultValue(DEFAULT_HOST) String contentApiServiceHost,
        @DefaultValue(DEFAULT_CONTENT_API_SERVICE_PORT) Integer contentApiServicePort,
        @DefaultValue(DEFAULT_FRONTEND_PORT) Integer frontendPort,
        @DefaultValue(DEFAULT_HOST) String analysisServiceHost,
        @DefaultValue(DEFAULT_ANALYSIS_SERVICE_PORT) Integer analysisServicePort,
        @DefaultValue(DEFAULT_HOST) String sourceIngestionServiceHost,
        @DefaultValue(DEFAULT_SOURCE_INGESTION_SERVICE_PORT) Integer sourceIngestionServicePort,
        @DefaultValue(DEFAULT_HOST) String deliveryServiceHost,
        @DefaultValue(DEFAULT_DELIVERY_SERVICE_PORT) Integer deliveryServicePort,
        String analysisStubResponseJson,
        String ingestionResponsesJson,
        String fixedNow,
        String contractAuthTokensJson) {
    private static final String DEFAULT_ENVIRONMENT = "dev";
    private static final String DEFAULT_HOST = "localhost";
    private static final String DEFAULT_CONTENT_API_SERVICE_PORT = "8000";
    private static final String DEFAULT_FRONTEND_PORT = "5173";
    private static final String DEFAULT_ANALYSIS_SERVICE_PORT = "8100";
    private static final String DEFAULT_SOURCE_INGESTION_SERVICE_PORT = "8200";
    private static final String DEFAULT_DELIVERY_SERVICE_PORT = "8300";
}
