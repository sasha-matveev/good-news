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
    void treatsPasswordlessStructuredOverridesAsExplicitDatabaseConfiguration() {
        DatabaseProperties properties = new DatabaseProperties(
            null,
            "db.internal",
            5432,
            "good_news",
            DatabaseProperties.DEFAULT_USER,
            null
        );

        assertThat(properties.isExplicitlyConfigured()).isTrue();
    }

    @Test
    void treatsPureDefaultsAsNoExplicitDatabaseConfiguration() {
        DatabaseProperties properties = new DatabaseProperties(
            null,
            DatabaseProperties.DEFAULT_HOST,
            Integer.valueOf(DatabaseProperties.DEFAULT_PORT),
            DatabaseProperties.DEFAULT_DATABASE,
            DatabaseProperties.DEFAULT_USER,
            null
        );

        assertThat(properties.isExplicitlyConfigured()).isFalse();
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
    void preservesUrlCredentialsWhenOnlyDefaultStructuredUserIsPresent() {
        DatabaseProperties properties = new DatabaseProperties(
            "postgresql+psycopg://legacy_user:legacy-pass@db.example:5544/good_news",
            "localhost",
            5432,
            "good_news",
            DatabaseProperties.DEFAULT_USER,
            null
        );

        String options = ReactiveDatabaseConfig.resolveConnectionFactoryOptions(properties).toString();

        assertThat(options).contains("user=legacy_user");
    }

    @Test
    void preservesPercentEncodedCredentialsDuringSqlAlchemyUrlNormalization() {
        assertThat(
            ReactiveDatabaseConfig.normalizeUrl(
                "postgresql+psycopg://legacy_user:p%40ss@db.example:5544/good_news?sslmode=require"
            )
        ).isEqualTo("r2dbc:postgresql://legacy_user:p%40ss@db.example:5544/good_news?ssl=true");
    }

    @Test
    void preservesQueryParametersDuringJdbcUrlNormalization() {
        assertThat(
            ReactiveDatabaseConfig.normalizeJdbcUrl(
                "postgresql+psycopg://legacy_user:p%40ss@db.example:5544/good_news?sslmode=require"
            )
        ).isEqualTo("jdbc:postgresql://legacy_user:p%40ss@db.example:5544/good_news?sslmode=require");
    }

    @Test
    void derivesJdbcConnectionOverridesFromLegacyUrlAndStructuredProperties() {
        DatabaseProperties properties = new DatabaseProperties(
            "postgresql+psycopg://legacy_user:legacy-pass@db.example:5544/good_news?sslmode=require",
            "localhost",
            5432,
            "good_news",
            "service_user",
            "top-secret"
        );

        JdbcDatabaseConnection connection = ReactiveDatabaseConfig.resolveJdbcConnection(properties);

        assertThat(connection.url()).isEqualTo(
            "jdbc:postgresql://legacy_user:legacy-pass@db.example:5544/good_news?sslmode=require"
        );
        assertThat(connection.user()).isEqualTo("service_user");
        assertThat(connection.password()).isEqualTo("top-secret");
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
