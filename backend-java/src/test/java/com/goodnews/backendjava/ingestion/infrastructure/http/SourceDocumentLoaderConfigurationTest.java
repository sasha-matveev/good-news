package com.goodnews.backendjava.ingestion.infrastructure.http;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.goodnews.backendjava.config.AppProperties;
import com.goodnews.backendjava.config.GoodNewsProperties;
import com.goodnews.backendjava.ingestion.application.port.SourceDocumentLoader;
import org.junit.jupiter.api.Test;
import org.springframework.web.reactive.function.client.WebClient;

class SourceDocumentLoaderConfigurationTest {

    private final SourceDocumentLoaderConfiguration configuration = new SourceDocumentLoaderConfiguration();
    private final GoodNewsProperties properties = mock(GoodNewsProperties.class);
    private final AppProperties appProperties = mock(AppProperties.class);
    private final PublicSourceUrlPolicy urlPolicy = mock(PublicSourceUrlPolicy.class);

    @Test
    void selectsDeterministicLoaderWhenResponsesAreConfigured() {
        when(properties.app()).thenReturn(appProperties);
        when(appProperties.ingestionResponsesJson()).thenReturn("{\"https://example.test/feed\":\"<rss/>\"}");

        SourceDocumentLoader loader =
                configuration.sourceDocumentLoader(properties, new ObjectMapper(), WebClient.builder(), urlPolicy);

        assertThat(loader).isInstanceOf(StubSourceDocumentLoader.class);
    }

    @Test
    void selectsLiveLoaderWhenResponsesAreNotConfigured() {
        when(properties.app()).thenReturn(appProperties);

        SourceDocumentLoader loader =
                configuration.sourceDocumentLoader(properties, new ObjectMapper(), WebClient.builder(), urlPolicy);

        assertThat(loader).isInstanceOf(WebClientSourceDocumentLoader.class);
    }
}
