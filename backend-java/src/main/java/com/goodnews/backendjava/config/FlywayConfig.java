package com.goodnews.backendjava.config;

import org.flywaydb.core.Flyway;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@ConditionalOnProperty(name = "spring.flyway.enabled", havingValue = "true", matchIfMissing = true)
public class FlywayConfig {

    @Bean(initMethod = "migrate")
    Flyway flyway(GoodNewsProperties properties) {
        JdbcDatabaseConnection connection = ReactiveDatabaseConfig.resolveJdbcConnection(properties.database());

        return Flyway.configure()
            .dataSource(connection.url(), connection.user(), connection.password())
            .locations("classpath:db/migration")
            .load();
    }
}
