package com.goodnews.backendjava.ingestion.application;

import com.goodnews.backendjava.ingestion.application.port.SourceReader;
import com.goodnews.backendjava.ingestion.application.port.SourceSyncWriter;
import com.goodnews.backendjava.ingestion.strategy.SourceIngestionStrategies;
import java.time.Clock;
import java.time.Instant;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

@Service
public final class SyncSingleSource {
    private final SourceReader sources;
    private final SourceSyncWriter writer;
    private final SourceIngestionStrategies strategies;
    private final Clock clock;

    public SyncSingleSource(
            SourceReader sources, SourceSyncWriter writer, SourceIngestionStrategies strategies, Clock clock) {
        this.sources = sources;
        this.writer = writer;
        this.strategies = strategies;
        this.clock = clock;
    }

    public Mono<SyncOutcome> sync(long sourceId) {
        Instant synchronizedAt = clock.instant();
        return sources.find(sourceId)
                .switchIfEmpty(Mono.error(new SourceNotFoundException(sourceId)))
                .flatMap(source -> strategies
                        .resolve(source.strategyKind())
                        .ingest(source)
                        .flatMap(posts -> writer.completeSuccessfulSync(source, posts, synchronizedAt))
                        .thenReturn(SyncOutcome.success(source.id())))
                .onErrorResume(
                        SourceIngestionException.class, failure -> writer.recordFailedSync(sourceId, synchronizedAt)
                                .thenReturn(SyncOutcome.failure()));
    }
}
