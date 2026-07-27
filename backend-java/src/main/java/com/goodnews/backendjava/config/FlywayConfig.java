package com.goodnews.backendjava.config;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@ConditionalOnProperty(name = "good-news.migration.run", havingValue = "true")
public class FlywayConfig {

    @Bean
    DatabaseMigrationRunner databaseMigrationRunner(GoodNewsProperties properties) {
        JdbcDatabaseConnection connection = new ConfiguredDatabase(properties.database()).jdbcConnection();
        return new DatabaseMigrationRunner(connection.url(), connection.user(), connection.password());
    }
}
