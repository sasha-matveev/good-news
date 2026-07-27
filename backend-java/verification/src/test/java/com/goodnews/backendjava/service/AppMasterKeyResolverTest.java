package com.goodnews.backendjava.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.goodnews.backendjava.config.AppProperties;
import com.goodnews.backendjava.config.AuthProperties;
import com.goodnews.backendjava.config.DatabaseProperties;
import com.goodnews.backendjava.config.EmailProperties;
import com.goodnews.backendjava.config.GeminiProperties;
import com.goodnews.backendjava.config.GoodNewsProperties;
import com.goodnews.backendjava.config.ObservabilityProperties;
import com.goodnews.backendjava.config.SchedulerProperties;
import org.junit.jupiter.api.Test;
import org.springframework.mock.env.MockEnvironment;

class AppMasterKeyResolverTest {

    @Test
    void requireFallsBackToRuntimeEnvironmentWhenBoundPropertyIsBlank() {
        AppMasterKeyResolver resolver = new AppMasterKeyResolver(
                propertiesWithAppMasterKey("   "),
                new MockEnvironment().withProperty("good-news.email.app-master-key", "runtime-master-key"));

        assertThat(resolver.require()).isEqualTo("runtime-master-key");
    }

    @Test
    void requireStillFailsWhenNoSupportedRuntimeSourceProvidesIt() {
        AppMasterKeyResolver resolver =
                new AppMasterKeyResolver(propertiesWithAppMasterKey(null), new MockEnvironment());

        assertThatThrownBy(resolver::require)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("GOOD_NEWS_APP_MASTER_KEY");
    }

    private GoodNewsProperties propertiesWithAppMasterKey(String appMasterKey) {
        return new GoodNewsProperties(
                new AppProperties(
                        "dev",
                        "localhost",
                        8000,
                        5173,
                        "localhost",
                        8100,
                        "localhost",
                        8200,
                        "localhost",
                        8300,
                        null,
                        null),
                new DatabaseProperties(null, "localhost", 5432, "good_news", "good_news", null),
                new AuthProperties(null, "", null),
                new SchedulerProperties(30, 3, null),
                new GeminiProperties(null, "gemini-3.1-flash-lite", 10, 8, 4),
                new EmailProperties(appMasterKey, null, null),
                new ObservabilityProperties(null, "127.0.0.1", 3000, "18:00"));
    }
}
