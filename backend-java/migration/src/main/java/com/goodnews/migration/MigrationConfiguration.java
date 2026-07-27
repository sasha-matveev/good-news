package com.goodnews.migration;

import com.goodnews.backendjava.config.ConfiguredDatabase;
import com.goodnews.backendjava.config.GoodNewsProperties;
import com.goodnews.backendjava.config.JdbcDatabaseConnection;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class MigrationConfiguration {

    @Bean(initMethod = "migrate")
    DatabaseMigrationRunner databaseMigrationRunner(GoodNewsProperties properties) {
        JdbcDatabaseConnection connection = new ConfiguredDatabase(properties.database()).jdbcConnection();
        return new DatabaseMigrationRunner(connection.url(), connection.user(), connection.password());
    }
}
