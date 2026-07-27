package com.goodnews.backendjava.ingestion.strategy;

import com.goodnews.backendjava.ingestion.model.CandidatePost;
import com.goodnews.backendjava.ingestion.model.SourceDefinition;
import com.goodnews.backendjava.ingestion.model.SourceStrategyKind;
import java.util.List;
import reactor.core.publisher.Mono;

public interface SourceIngestionStrategy {
    SourceStrategyKind kind();

    Mono<List<CandidatePost>> ingest(SourceDefinition source);
}
