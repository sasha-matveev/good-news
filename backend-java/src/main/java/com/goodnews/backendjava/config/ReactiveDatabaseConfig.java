package com.goodnews.backendjava.config;

import io.r2dbc.spi.ConnectionFactories;
import io.r2dbc.spi.ConnectionFactory;
import io.r2dbc.spi.ConnectionFactoryOptions;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.r2dbc.core.R2dbcEntityTemplate;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.util.StringUtils;

import java.net.URI;
import java.net.URISyntaxException;

import static io.r2dbc.spi.ConnectionFactoryOptions.DATABASE;
import static io.r2dbc.spi.ConnectionFactoryOptions.DRIVER;
import static io.r2dbc.spi.ConnectionFactoryOptions.HOST;
import static io.r2dbc.spi.ConnectionFactoryOptions.PASSWORD;
import static io.r2dbc.spi.ConnectionFactoryOptions.PORT;
import static io.r2dbc.spi.ConnectionFactoryOptions.USER;

@Configuration
public class ReactiveDatabaseConfig {

    private static final String POSTGRES_DRIVER = "postgresql";

    @Bean
    ConnectionFactory connectionFactory(GoodNewsProperties properties) {
        return ConnectionFactories.get(resolveConnectionFactoryOptions(properties.database()));
    }

    @Bean
    DatabaseClient databaseClient(ConnectionFactory connectionFactory) {
        return DatabaseClient.builder()
            .connectionFactory(connectionFactory)
            .build();
    }

    @Bean
    R2dbcEntityTemplate r2dbcEntityTemplate(ConnectionFactory connectionFactory) {
        return new R2dbcEntityTemplate(connectionFactory);
    }

    static ConnectionFactoryOptions resolveConnectionFactoryOptions(DatabaseProperties properties) {
        if (StringUtils.hasText(properties.url())) {
            return normalizeUrlOptions(properties);
        }

        ConnectionFactoryOptions.Builder builder = ConnectionFactoryOptions.builder()
            .option(DRIVER, POSTGRES_DRIVER)
            .option(HOST, properties.postgresHost())
            .option(PORT, properties.postgresPort())
            .option(DATABASE, properties.postgresDatabase())
            .option(USER, properties.postgresUser());

        if (StringUtils.hasText(properties.postgresPassword())) {
            builder.option(PASSWORD, properties.postgresPassword());
        }

        return builder.build();
    }

    private static ConnectionFactoryOptions normalizeUrlOptions(DatabaseProperties properties) {
        String normalizedUrl = normalizeUrl(properties.url());
        ConnectionFactoryOptions baseOptions = ConnectionFactoryOptions.parse(normalizedUrl);
        ConnectionFactoryOptions.Builder builder = ConnectionFactoryOptions.builder().from(baseOptions);

        if (StringUtils.hasText(properties.postgresUser())) {
            builder.option(USER, properties.postgresUser());
        }
        if (StringUtils.hasText(properties.postgresPassword())) {
            builder.option(PASSWORD, properties.postgresPassword());
        }

        return builder.build();
    }

    private static String normalizeUrl(String url) {
        if (url.startsWith("r2dbc:")) {
            return url;
        }
        if (url.startsWith("postgresql+")) {
            return rewriteSqlAlchemyStyleUrl(url);
        }
        if (url.startsWith("jdbc:postgresql://")) {
            return "r2dbc:postgresql://" + url.substring("jdbc:postgresql://".length());
        }
        if (url.startsWith("postgresql://")) {
            return "r2dbc:postgresql://" + url.substring("postgresql://".length());
        }
        throw new IllegalArgumentException("Unsupported GOOD_NEWS_DATABASE_URL scheme: " + url);
    }

    private static String rewriteSqlAlchemyStyleUrl(String url) {
        try {
            URI uri = new URI(url);
            StringBuilder builder = new StringBuilder("r2dbc:postgresql://");

            if (StringUtils.hasText(uri.getUserInfo())) {
                builder.append(uri.getUserInfo()).append('@');
            }

            builder.append(uri.getHost());

            if (uri.getPort() != -1) {
                builder.append(':').append(uri.getPort());
            }

            builder.append(uri.getPath());

            String query = toReactiveQuery(uri.getQuery());
            if (StringUtils.hasText(query)) {
                builder.append('?').append(query);
            }

            return builder.toString();
        } catch (URISyntaxException exception) {
            throw new IllegalArgumentException("Invalid GOOD_NEWS_DATABASE_URL value", exception);
        }
    }

    private static String toReactiveQuery(String query) {
        if (!StringUtils.hasText(query)) {
            return null;
        }

        StringBuilder builder = new StringBuilder();
        for (String queryPart : query.split("&")) {
            String normalizedPart = queryPart;
            String[] keyValue = queryPart.split("=", 2);
            if (keyValue.length == 2 && "sslmode".equals(keyValue[0])) {
                normalizedPart = "ssl=" + !"disable".equalsIgnoreCase(keyValue[1]);
            }

            if (!builder.isEmpty()) {
                builder.append('&');
            }
            builder.append(normalizedPart);
        }
        return builder.toString();
    }
}
