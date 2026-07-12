package com.goodnews.backendjava.config;

import org.flywaydb.core.Flyway;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Condition;
import org.springframework.context.annotation.ConditionContext;
import org.springframework.context.annotation.Conditional;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.type.AnnotatedTypeMetadata;

@Configuration
@ConditionalOnProperty(name = "spring.flyway.enabled", havingValue = "true", matchIfMissing = true)
@Conditional(DatabaseConfiguredCondition.class)
public class FlywayConfig {

    @Bean(initMethod = "migrate")
    Flyway flyway(GoodNewsProperties properties) {
        JdbcDatabaseConnection connection = new ConfiguredDatabase(properties.database()).jdbcConnection();

        return Flyway.configure()
                .dataSource(connection.url(), connection.user(), connection.password())
                .locations("classpath:db/migration")
                .load();
    }
}

class DatabaseConfiguredCondition implements Condition {

    @Override
    public boolean matches(ConditionContext context, AnnotatedTypeMetadata metadata) {
        DatabaseProperties properties = Binder.get(context.getEnvironment())
                .bind("good-news.database", DatabaseProperties.class)
                .orElseGet(() -> new DatabaseProperties(
                        null,
                        DatabaseProperties.DEFAULT_HOST,
                        Integer.valueOf(DatabaseProperties.DEFAULT_PORT),
                        DatabaseProperties.DEFAULT_DATABASE,
                        DatabaseProperties.DEFAULT_USER,
                        null));
        return properties.isExplicitlyConfigured();
    }
}
