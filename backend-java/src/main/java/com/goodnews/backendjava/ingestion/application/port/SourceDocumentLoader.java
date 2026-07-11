package com.goodnews.backendjava.ingestion.application.port;

import reactor.core.publisher.Mono;

public interface SourceDocumentLoader {
    Mono<String> load(String url);

    Mono<Void> validate(String url);
}
