package com.goodnews.backendjava.service;

import com.goodnews.backendjava.config.GoodNewsProperties;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

@Component
final class AppMasterKeyResolver {

    private final GoodNewsProperties properties;
    private final Environment environment;

    AppMasterKeyResolver(GoodNewsProperties properties, Environment environment) {
        this.properties = properties;
        this.environment = environment;
    }

    String require() {
        String configured = properties.email().appMasterKey();
        if (hasText(configured)) {
            return configured;
        }
        String runtimeConfigured = environment.getProperty("good-news.email.app-master-key");
        if (hasText(runtimeConfigured)) {
            return runtimeConfigured;
        }
        runtimeConfigured = environment.getProperty("GOOD_NEWS_APP_MASTER_KEY");
        if (hasText(runtimeConfigured)) {
            return runtimeConfigured;
        }
        throw new IllegalStateException(
                "Missing app master key contract GOOD_NEWS_APP_MASTER_KEY; set it explicitly for SMTP secret encryption.");
    }

    private boolean hasText(String value) {
        return value != null && !value.isBlank();
    }
}
