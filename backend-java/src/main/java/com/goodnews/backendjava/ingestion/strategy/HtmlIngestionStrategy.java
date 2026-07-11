package com.goodnews.backendjava.ingestion.strategy;

import com.goodnews.backendjava.ingestion.application.SourceIngestionException;
import com.goodnews.backendjava.ingestion.application.port.SourceDocumentLoader;
import com.goodnews.backendjava.ingestion.model.CandidatePost;
import com.goodnews.backendjava.ingestion.model.SourceDefinition;
import com.goodnews.backendjava.ingestion.model.SourceStrategyKind;
import com.goodnews.backendjava.ingestion.parsing.HtmlListingParser;
import java.util.List;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

@Component
public final class HtmlIngestionStrategy implements SourceIngestionStrategy {
    private final SourceDocumentLoader documents;
    private final HtmlListingParser parser;
    private final ListingEnricher enricher;

    public HtmlIngestionStrategy(SourceDocumentLoader documents, HtmlListingParser parser, ListingEnricher enricher) {
        this.documents = documents;
        this.parser = parser;
        this.enricher = enricher;
    }

    @Override
    public SourceStrategyKind kind() {
        return SourceStrategyKind.HTML;
    }

    @Override
    public Mono<List<CandidatePost>> ingest(SourceDefinition source) {
        String listingUrl = valueOr(source.options().listingUrl(), source.originalUrl());
        String selector = valueOr(source.options().linkSelector(), "a");
        return documents
                .load(listingUrl)
                .publishOn(Schedulers.boundedElastic())
                .map(html -> parser.parse(html, selector))
                .flatMap(items -> items.isEmpty()
                        ? Mono.error(new SourceIngestionException(
                                "No links found on listing page using selector '" + selector + "'"))
                        : enricher.enrich(listingUrl, items));
    }

    private static String valueOr(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }
}
