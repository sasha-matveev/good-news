package com.goodnews.backendjava.config;

import org.flywaydb.core.Flyway;
import org.springframework.context.annotation.Condition;
import org.springframework.context.annotation.ConditionContext;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Conditional;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.type.AnnotatedTypeMetadata;

@Configuration
@ConditionalOnProperty(name = "spring.flyway.enabled", havingValue = "true", matchIfMissing = true)
@Conditional(DatabaseConfiguredCondition.class)
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

class DatabaseConfiguredCondition implements Condition {

    @Override
    public boolean matches(ConditionContext context, AnnotatedTypeMetadata metadata) {
        String url = context.getEnvironment().getProperty("good-news.database.url");
        String password = context.getEnvironment().getProperty("good-news.database.postgres-password");
        return hasText(url) || hasText(password);
    }

    private boolean hasText(String value) {
        return value != null && !value.isBlank();
    }
}
