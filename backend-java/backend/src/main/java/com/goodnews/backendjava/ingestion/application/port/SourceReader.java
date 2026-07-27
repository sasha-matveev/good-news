package com.goodnews.backendjava.ingestion.application.port;

import com.goodnews.backendjava.ingestion.model.SourceDefinition;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface SourceReader {
    Mono<SourceDefinition> find(long sourceId);

    Flux<Long> findActiveIdsOrdered();
}
