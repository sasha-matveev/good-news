package com.goodnews.backendjava.config;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class ReactiveDatabaseConfigTest {

    @Test
    void derivesReactiveConnectionOptionsFromStructuredProperties() {
        DatabaseProperties properties = new DatabaseProperties(
            null,
            "db.internal",
            6432,
            "good_news_prod",
            "service_user",
            "top-secret"
        );

        String options = ReactiveDatabaseConfig.resolveConnectionFactoryOptions(properties).toString();

        assertThat(options).contains("driver=postgresql");
        assertThat(options).contains("host=db.internal");
        assertThat(options).contains("port=6432");
        assertThat(options).contains("database=good_news_prod");
        assertThat(options).contains("user=service_user");
    }

    @Test
    void normalizesLegacySqlAlchemyUrlOverridesToReactiveOptions() {
        DatabaseProperties properties = new DatabaseProperties(
            "postgresql+psycopg://legacy_user:legacy-pass@db.example:5544/good_news?sslmode=require",
            "localhost",
            5432,
            "good_news",
            "service_user",
            "top-secret"
        );

        String options = ReactiveDatabaseConfig.resolveConnectionFactoryOptions(properties).toString();

        assertThat(options).contains("driver=postgresql");
        assertThat(options).contains("host=db.example");
        assertThat(options).contains("port=5544");
        assertThat(options).contains("database=good_news");
        assertThat(options).contains("user=service_user");
    }

    @Test
    void rejectsUnsupportedUrlSchemesEarly() {
        DatabaseProperties properties = new DatabaseProperties(
            "mysql://db.example/good_news",
            "localhost",
            5432,
            "good_news",
            "service_user",
            "top-secret"
        );

        org.assertj.core.api.Assertions.assertThatThrownBy(
            () -> ReactiveDatabaseConfig.resolveConnectionFactoryOptions(properties)
        ).isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("Unsupported GOOD_NEWS_DATABASE_URL scheme");
    }
}
