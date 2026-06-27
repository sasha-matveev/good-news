package com.goodnews.backendjava.config;

import org.springframework.boot.context.properties.bind.DefaultValue;

public record GeminiProperties(
    String apiKey,
    @DefaultValue(DEFAULT_MODEL) String model,
    @DefaultValue(DEFAULT_BATCH_SIZE) Integer batchSize,
    @DefaultValue(DEFAULT_MAX_RPM) Integer maxRpm,
    @DefaultValue(DEFAULT_MAX_RETRIES) Integer maxRetries
) {
    private static final String DEFAULT_MODEL = "gemini-3.1-flash-lite";
    private static final String DEFAULT_BATCH_SIZE = "10";
    private static final String DEFAULT_MAX_RPM = "8";
    private static final String DEFAULT_MAX_RETRIES = "4";
}
