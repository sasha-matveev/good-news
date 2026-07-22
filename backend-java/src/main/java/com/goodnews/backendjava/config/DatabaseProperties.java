package com.goodnews.backendjava.config;

import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.PositiveOrZero;
import java.time.Duration;
import org.springframework.boot.context.properties.bind.ConstructorBinding;
import org.springframework.boot.context.properties.bind.DefaultValue;
import org.springframework.util.StringUtils;

public record DatabaseProperties(
        String url,
        @DefaultValue(DEFAULT_HOST) String postgresHost,
        @DefaultValue(DEFAULT_PORT) Integer postgresPort,
        @DefaultValue(DEFAULT_DATABASE) String postgresDatabase,
        @DefaultValue(DEFAULT_USER) String postgresUser,
        String postgresPassword,
        @PositiveOrZero @DefaultValue("0") Integer poolInitialSize,
        @Positive @DefaultValue("5") Integer poolMaxSize,
        @DefaultValue("2s") Duration poolAcquireTimeout,
        @DefaultValue("5s") Duration connectTimeout,
        @DefaultValue("30s") Duration operationTimeout,
        @DefaultValue("10m") Duration poolIdleTimeout,
        @DefaultValue("30m") Duration poolMaxLifeTime) {
    static final String DEFAULT_HOST = "localhost";
    static final String DEFAULT_PORT = "5432";
    static final String DEFAULT_DATABASE = "good_news";
    static final String DEFAULT_USER = "good_news";

    @ConstructorBinding
    public DatabaseProperties {}

    public DatabaseProperties(
            String url,
            String postgresHost,
            Integer postgresPort,
            String postgresDatabase,
            String postgresUser,
            String postgresPassword) {
        this(
                url,
                postgresHost,
                postgresPort,
                postgresDatabase,
                postgresUser,
                postgresPassword,
                0,
                5,
                Duration.ofSeconds(2),
                Duration.ofSeconds(5),
                Duration.ofSeconds(30),
                Duration.ofMinutes(10),
                Duration.ofMinutes(30));
    }

    @AssertTrue(message = "GOOD_NEWS_DATABASE_POOL_INITIAL_SIZE must not exceed GOOD_NEWS_DATABASE_POOL_MAX_SIZE.")
    public boolean isPoolSizeValid() {
        return poolInitialSize <= poolMaxSize;
    }

    public boolean isExplicitlyConfigured() {
        return StringUtils.hasText(url)
                || StringUtils.hasText(postgresPassword)
                || !DEFAULT_HOST.equals(postgresHost)
                || !Integer.valueOf(DEFAULT_PORT).equals(postgresPort)
                || !DEFAULT_DATABASE.equals(postgresDatabase)
                || !DEFAULT_USER.equals(postgresUser);
    }

    boolean hasExplicitUserOverride() {
        return StringUtils.hasText(postgresUser) && !DEFAULT_USER.equals(postgresUser);
    }
}
