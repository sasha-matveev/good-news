package com.goodnews.backendjava.config;

import static io.r2dbc.spi.ConnectionFactoryOptions.PASSWORD;
import static io.r2dbc.spi.ConnectionFactoryOptions.USER;

import io.r2dbc.spi.ConnectionFactoryOptions;
import io.r2dbc.spi.Option;
import org.springframework.util.StringUtils;

final class DatabaseUrl {

    private final String value;

    DatabaseUrl(String value) {
        this.value = value;
    }

    String reactive() {
        if (this.value.startsWith("r2dbc:")) {
            return this.value;
        }
        if (this.value.startsWith("postgresql+")) {
            return "r2dbc:postgresql://" + this.authorityAndPathWithReactiveQuery();
        }
        if (this.value.startsWith("jdbc:postgresql://")) {
            return "r2dbc:postgresql://" + this.value.substring("jdbc:postgresql://".length());
        }
        if (this.value.startsWith("postgresql://")) {
            return "r2dbc:postgresql://" + this.value.substring("postgresql://".length());
        }
        throw new IllegalArgumentException("Unsupported GOOD_NEWS_DATABASE_URL scheme: " + this.value);
    }

    String jdbc() {
        if (this.value.startsWith("jdbc:postgresql://")) {
            return "jdbc:postgresql://" + this.authorityAndPathWithoutUserInfo();
        }
        if (this.value.startsWith("r2dbc:postgresql://")) {
            return "jdbc:postgresql://" + this.authorityAndPathWithoutUserInfo();
        }
        if (this.value.startsWith("postgresql+")) {
            return "jdbc:postgresql://" + this.authorityAndPathWithoutUserInfo();
        }
        if (this.value.startsWith("postgresql://")) {
            return "jdbc:postgresql://" + this.authorityAndPathWithoutUserInfo();
        }
        throw new IllegalArgumentException("Unsupported GOOD_NEWS_DATABASE_URL scheme: " + this.value);
    }

    ConnectionFactoryOptions connectionFactoryOptions(String user, String password) {
        ConnectionFactoryOptions.Builder builder =
                ConnectionFactoryOptions.builder().from(this.reactiveOptions());
        if (StringUtils.hasText(user)) {
            builder.option(USER, user);
        }
        if (StringUtils.hasText(password)) {
            builder.option(PASSWORD, password);
        }
        return builder.build();
    }

    String user() {
        return this.optionAsString(USER);
    }

    String password() {
        return this.optionAsString(PASSWORD);
    }

    private ConnectionFactoryOptions reactiveOptions() {
        return ConnectionFactoryOptions.parse(this.reactive());
    }

    private String optionAsString(Option<?> option) {
        Object resolved = this.reactiveOptions().getValue(option);
        return resolved == null ? null : resolved.toString();
    }

    private String authorityAndPathWithReactiveQuery() {
        String[] baseAndQuery = this.authorityAndPath().split("\\?", 2);
        if (baseAndQuery.length == 1) {
            return baseAndQuery[0];
        }
        String query = this.reactiveQuery(baseAndQuery[1]);
        if (!StringUtils.hasText(query)) {
            return baseAndQuery[0];
        }
        return baseAndQuery[0] + '?' + query;
    }

    private String authorityAndPath() {
        int schemeSeparatorIndex = this.value.indexOf("://");
        if (schemeSeparatorIndex < 0) {
            throw new IllegalArgumentException("Invalid GOOD_NEWS_DATABASE_URL value: " + this.value);
        }
        return this.value.substring(schemeSeparatorIndex + 3);
    }

    private String authorityAndPathWithoutUserInfo() {
        String authorityAndPath = this.authorityAndPath();
        int authorityEnd = authorityAndPath.indexOf('/');
        int searchEnd = authorityEnd < 0 ? authorityAndPath.length() : authorityEnd;
        int userInfoEnd = authorityAndPath.lastIndexOf('@', searchEnd);
        return userInfoEnd < 0 ? authorityAndPath : authorityAndPath.substring(userInfoEnd + 1);
    }

    private String reactiveQuery(String query) {
        if (!StringUtils.hasText(query)) {
            return null;
        }
        StringBuilder builder = new StringBuilder();
        for (String queryPart : query.split("&")) {
            String normalized = queryPart;
            String[] keyValue = queryPart.split("=", 2);
            if (keyValue.length == 2 && "sslmode".equals(keyValue[0])) {
                normalized = "ssl=" + !"disable".equalsIgnoreCase(keyValue[1]);
            }
            if (!builder.isEmpty()) {
                builder.append('&');
            }
            builder.append(normalized);
        }
        return builder.toString();
    }
}
