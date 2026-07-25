package com.goodnews.backendjava.contract;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.goodnews.backendjava.ingestion.application.SourceIngestionException;
import com.goodnews.backendjava.ingestion.application.port.SourceDocumentLoader;
import java.util.Map;
import reactor.core.publisher.Mono;

final class ContractSourceDocumentLoader implements SourceDocumentLoader {

    private final Map<String, String> responses;

    ContractSourceDocumentLoader(String json, ObjectMapper objectMapper) {
        try {
            responses = Map.copyOf(objectMapper.readValue(json, new TypeReference<>() {}));
        } catch (Exception exception) {
            throw new IllegalArgumentException("Invalid contract source fixture", exception);
        }
    }

    @Override
    public Mono<String> load(String url) {
        String response = responses.get(url);
        return response == null
                ? Mono.error(new SourceIngestionException("No contract response for source URL"))
                : Mono.just(response);
    }

    @Override
    public Mono<Void> validate(String url) {
        return responses.containsKey(url)
                ? Mono.empty()
                : Mono.error(new SourceIngestionException("No contract response for source URL"));
    }
}
