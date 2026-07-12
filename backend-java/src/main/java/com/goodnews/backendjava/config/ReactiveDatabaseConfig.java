package com.goodnews.backendjava.config;

import io.r2dbc.spi.ConnectionFactories;
import io.r2dbc.spi.ConnectionFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.r2dbc.core.R2dbcEntityTemplate;
import org.springframework.r2dbc.core.DatabaseClient;

@Configuration
public class ReactiveDatabaseConfig {

    @Bean
    ConnectionFactory connectionFactory(GoodNewsProperties properties) {
        return ConnectionFactories.get(new ConfiguredDatabase(properties.database()).connectionFactoryOptions());
    }

    @Bean
    DatabaseClient databaseClient(ConnectionFactory connectionFactory) {
        return DatabaseClient.builder().connectionFactory(connectionFactory).build();
    }

    @Bean
    R2dbcEntityTemplate r2dbcEntityTemplate(ConnectionFactory connectionFactory) {
        return new R2dbcEntityTemplate(connectionFactory);
    }
}

record JdbcDatabaseConnection(String url, String user, String password) {}
