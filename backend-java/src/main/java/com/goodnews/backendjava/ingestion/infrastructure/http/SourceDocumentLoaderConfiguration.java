package com.goodnews.backendjava.ingestion.infrastructure.http;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.goodnews.backendjava.config.GoodNewsProperties;
import com.goodnews.backendjava.ingestion.application.port.SourceDocumentLoader;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
public class SourceDocumentLoaderConfiguration {

    @Bean
    SourceDocumentLoader sourceDocumentLoader(
            GoodNewsProperties properties,
            ObjectMapper objectMapper,
            WebClient.Builder clientBuilder,
            PublicSourceUrlPolicy urlPolicy) {
        String deterministicResponses = properties.app().ingestionResponsesJson();
        if (deterministicResponses != null && !deterministicResponses.isBlank()) {
            return new StubSourceDocumentLoader(deterministicResponses, objectMapper);
        }
        return new WebClientSourceDocumentLoader(clientBuilder, urlPolicy);
    }
}
