package com.goodnews.backendjava.config;

import static io.r2dbc.postgresql.PostgresqlConnectionFactoryProvider.APPLICATION_NAME;
import static io.r2dbc.spi.ConnectionFactoryOptions.CONNECT_TIMEOUT;
import static io.r2dbc.spi.ConnectionFactoryOptions.DATABASE;
import static io.r2dbc.spi.ConnectionFactoryOptions.DRIVER;
import static io.r2dbc.spi.ConnectionFactoryOptions.HOST;
import static io.r2dbc.spi.ConnectionFactoryOptions.PASSWORD;
import static io.r2dbc.spi.ConnectionFactoryOptions.PORT;
import static io.r2dbc.spi.ConnectionFactoryOptions.STATEMENT_TIMEOUT;
import static io.r2dbc.spi.ConnectionFactoryOptions.USER;

import io.r2dbc.spi.ConnectionFactoryOptions;
import org.springframework.util.StringUtils;

final class ConfiguredDatabase {

    private static final String POSTGRES_DRIVER = "postgresql";

    private final DatabaseProperties properties;

    ConfiguredDatabase(DatabaseProperties properties) {
        this.properties = properties;
    }

    ConnectionFactoryOptions connectionFactoryOptions() {
        ConnectionFactoryOptions baseOptions;
        if (StringUtils.hasText(this.properties.url())) {
            baseOptions = this.urlBasedDatabase()
                    .connectionFactoryOptions(
                            this.properties.hasExplicitUserOverride() ? this.properties.postgresUser() : null,
                            this.properties.postgresPassword());
        } else {
            ConnectionFactoryOptions.Builder builder = ConnectionFactoryOptions.builder()
                    .option(DRIVER, POSTGRES_DRIVER)
                    .option(HOST, this.properties.postgresHost())
                    .option(PORT, this.properties.postgresPort())
                    .option(DATABASE, this.properties.postgresDatabase())
                    .option(USER, this.properties.postgresUser());
            if (StringUtils.hasText(this.properties.postgresPassword())) {
                builder.option(PASSWORD, this.properties.postgresPassword());
            }
            baseOptions = builder.build();
        }
        return ConnectionFactoryOptions.builder()
                .from(baseOptions)
                .option(APPLICATION_NAME, "good-news-java")
                .option(CONNECT_TIMEOUT, this.properties.connectTimeout())
                .option(STATEMENT_TIMEOUT, this.properties.operationTimeout())
                .build();
    }

    JdbcDatabaseConnection jdbcConnection() {
        if (StringUtils.hasText(this.properties.url())) {
            DatabaseUrl databaseUrl = this.urlBasedDatabase();
            return new JdbcDatabaseConnection(
                    databaseUrl.jdbc(),
                    this.properties.hasExplicitUserOverride() ? this.properties.postgresUser() : databaseUrl.user(),
                    StringUtils.hasText(this.properties.postgresPassword())
                            ? this.properties.postgresPassword()
                            : databaseUrl.password());
        }
        return new JdbcDatabaseConnection(
                "jdbc:postgresql://%s:%s/%s"
                        .formatted(
                                this.properties.postgresHost(),
                                this.properties.postgresPort(),
                                this.properties.postgresDatabase()),
                this.properties.postgresUser(),
                this.properties.postgresPassword());
    }

    private DatabaseUrl urlBasedDatabase() {
        return new DatabaseUrl(this.properties.url());
    }
}
