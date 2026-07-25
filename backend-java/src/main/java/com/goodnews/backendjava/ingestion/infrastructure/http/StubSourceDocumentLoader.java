package com.goodnews.backendjava.ingestion.infrastructure.http;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.goodnews.backendjava.ingestion.application.SourceIngestionException;
import com.goodnews.backendjava.ingestion.application.port.SourceDocumentLoader;
import java.util.Map;
import reactor.core.publisher.Mono;

public final class StubSourceDocumentLoader implements SourceDocumentLoader {

    private final Map<String, String> responses;

    public StubSourceDocumentLoader(String json, ObjectMapper objectMapper) {
        try {
            this.responses = objectMapper.readValue(json, new TypeReference<>() {});
        } catch (Exception exception) {
            throw new IllegalArgumentException("Invalid GOOD_NEWS_INGESTION_RESPONSES_JSON", exception);
        }
    }

    @Override
    public Mono<String> load(String url) {
        String response = this.responses.get(url);
        if (response == null) {
            return Mono.error(new SourceIngestionException("No deterministic response for source URL"));
        }
        return Mono.just(response);
    }

    @Override
    public Mono<Void> validate(String url) {
        return this.responses.containsKey(url)
                ? Mono.empty()
                : Mono.error(new SourceIngestionException("No deterministic response for source URL"));
    }
}
