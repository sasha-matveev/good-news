package com.goodnews.backendjava.config;

import org.springframework.boot.context.properties.bind.DefaultValue;

public record DatabaseProperties(
    String url,
    @DefaultValue(DEFAULT_HOST) String postgresHost,
    @DefaultValue(DEFAULT_PORT) Integer postgresPort,
    @DefaultValue(DEFAULT_DATABASE) String postgresDatabase,
    @DefaultValue(DEFAULT_USER) String postgresUser,
    String postgresPassword
) {
    private static final String DEFAULT_HOST = "localhost";
    private static final String DEFAULT_PORT = "5432";
    private static final String DEFAULT_DATABASE = "good_news";
    private static final String DEFAULT_USER = "good_news";
}
