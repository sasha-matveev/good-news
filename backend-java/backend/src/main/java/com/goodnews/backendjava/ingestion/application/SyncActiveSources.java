package com.goodnews.backendjava.ingestion.application;

import com.goodnews.backendjava.ingestion.application.port.SourceReader;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

@Service
public final class SyncActiveSources {
    private final SourceReader sources;
    private final SyncSingleSource singleSource;
    private final int concurrency;

    public SyncActiveSources(
            SourceReader sources,
            SyncSingleSource singleSource,
            @Value("${good-news.ingestion.bulk-concurrency:4}") int concurrency) {
        if (concurrency < 1) {
            throw new IllegalArgumentException("good-news.ingestion.bulk-concurrency must be at least 1");
        }
        this.sources = sources;
        this.singleSource = singleSource;
        this.concurrency = concurrency;
    }

    public Mono<SyncOutcome> sync() {
        return sources.findActiveIdsOrdered()
                .flatMapSequential(singleSource::sync, concurrency)
                .filter(outcome -> !outcome.processedSourceIds().isEmpty())
                .flatMapIterable(SyncOutcome::processedSourceIds)
                .collectList()
                .map(ids -> new SyncOutcome(List.copyOf(ids)));
    }
}
