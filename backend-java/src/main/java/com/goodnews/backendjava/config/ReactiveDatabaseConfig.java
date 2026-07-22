package com.goodnews.backendjava.config;

import io.r2dbc.pool.ConnectionPool;
import io.r2dbc.pool.ConnectionPoolConfiguration;
import io.r2dbc.spi.ConnectionFactories;
import io.r2dbc.spi.ConnectionFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.r2dbc.core.R2dbcEntityTemplate;
import org.springframework.r2dbc.core.DatabaseClient;

@Configuration
public class ReactiveDatabaseConfig {

    @Bean(destroyMethod = "dispose")
    ConnectionFactory connectionFactory(GoodNewsProperties properties) {
        ConnectionFactory driver =
                ConnectionFactories.get(new ConfiguredDatabase(properties.database()).connectionFactoryOptions());
        DatabaseProperties database = properties.database();
        ConnectionPoolConfiguration poolConfiguration = ConnectionPoolConfiguration.builder(driver)
                .name("good-news-java")
                .initialSize(database.poolInitialSize())
                .maxSize(database.poolMaxSize())
                .maxAcquireTime(database.poolAcquireTimeout())
                .maxCreateConnectionTime(database.connectTimeout())
                .maxIdleTime(database.poolIdleTimeout())
                .maxLifeTime(database.poolMaxLifeTime())
                .validationQuery("SELECT 1")
                .build();
        return new ConnectionPool(poolConfiguration);
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
