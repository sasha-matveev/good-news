package com.goodnews.backendjava.ingestion.infrastructure.http;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.goodnews.backendjava.config.GoodNewsProperties;
import com.goodnews.backendjava.ingestion.application.port.SourceDocumentLoader;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
public class SourceDocumentLoaderConfiguration {

    @Bean
    @ConditionalOnProperty(name = "good-news.app.ingestion-responses-json")
    SourceDocumentLoader stubSourceDocumentLoader(GoodNewsProperties properties, ObjectMapper objectMapper) {
        return new StubSourceDocumentLoader(properties.app().ingestionResponsesJson(), objectMapper);
    }

    @Bean
    @ConditionalOnProperty(name = "good-news.app.ingestion-responses-json", matchIfMissing = true)
    SourceDocumentLoader liveSourceDocumentLoader(WebClient.Builder clientBuilder, PublicSourceUrlPolicy urlPolicy) {
        return new WebClientSourceDocumentLoader(clientBuilder, urlPolicy);
    }
}
