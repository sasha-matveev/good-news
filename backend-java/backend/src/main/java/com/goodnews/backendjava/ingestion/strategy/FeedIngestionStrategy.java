package com.goodnews.backendjava.ingestion.strategy;

import com.goodnews.backendjava.ingestion.application.SourceIngestionException;
import com.goodnews.backendjava.ingestion.application.port.SourceDocumentLoader;
import com.goodnews.backendjava.ingestion.model.CandidatePost;
import com.goodnews.backendjava.ingestion.model.SourceDefinition;
import com.goodnews.backendjava.ingestion.model.SourceStrategyKind;
import com.goodnews.backendjava.ingestion.parsing.FeedDocumentParser;
import java.util.List;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

@Component
public final class FeedIngestionStrategy implements SourceIngestionStrategy {
    private final SourceDocumentLoader documents;
    private final FeedDocumentParser parser;

    public FeedIngestionStrategy(SourceDocumentLoader documents, FeedDocumentParser parser) {
        this.documents = documents;
        this.parser = parser;
    }

    @Override
    public SourceStrategyKind kind() {
        return SourceStrategyKind.FEED;
    }

    @Override
    public Mono<List<CandidatePost>> ingest(SourceDefinition source) {
        if (source.feedUrl() == null || source.feedUrl().isBlank()) {
            return Mono.error(new SourceIngestionException("Feed strategy is missing a feed URL"));
        }
        return documents
                .load(source.feedUrl())
                .publishOn(Schedulers.boundedElastic())
                .map(parser::parse)
                .onErrorMap(
                        IllegalArgumentException.class,
                        error -> new SourceIngestionException("Stored feed response could not be parsed", error))
                .map(posts -> RecentCandidates.posts(posts, source.lastSuccessAt()));
    }
}
