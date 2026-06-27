package com.goodnews.backendjava.config;

import org.springframework.boot.context.properties.bind.DefaultValue;
import org.springframework.util.StringUtils;

public record DatabaseProperties(
    String url,
    @DefaultValue(DEFAULT_HOST) String postgresHost,
    @DefaultValue(DEFAULT_PORT) Integer postgresPort,
    @DefaultValue(DEFAULT_DATABASE) String postgresDatabase,
    @DefaultValue(DEFAULT_USER) String postgresUser,
    String postgresPassword
) {
    static final String DEFAULT_HOST = "localhost";
    static final String DEFAULT_PORT = "5432";
    static final String DEFAULT_DATABASE = "good_news";
    static final String DEFAULT_USER = "good_news";

    boolean isExplicitlyConfigured() {
        return StringUtils.hasText(url)
            || StringUtils.hasText(postgresPassword)
            || !DEFAULT_HOST.equals(postgresHost)
            || !Integer.valueOf(DEFAULT_PORT).equals(postgresPort)
            || !DEFAULT_DATABASE.equals(postgresDatabase)
            || !DEFAULT_USER.equals(postgresUser);
    }
}
