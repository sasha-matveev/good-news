package com.goodnews.backendjava.ingestion.strategy;

import com.goodnews.backendjava.ingestion.application.SourceIngestionException;
import com.goodnews.backendjava.ingestion.application.port.SourceDocumentLoader;
import com.goodnews.backendjava.ingestion.knownsite.KnownSiteParser;
import com.goodnews.backendjava.ingestion.knownsite.KnownSiteParsers;
import com.goodnews.backendjava.ingestion.model.CandidatePost;
import com.goodnews.backendjava.ingestion.model.SourceDefinition;
import com.goodnews.backendjava.ingestion.model.SourceStrategyKind;
import java.util.List;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

@Component
public final class KnownSiteIngestionStrategy implements SourceIngestionStrategy {
    private final SourceDocumentLoader documents;
    private final KnownSiteParsers parsers;
    private final ListingEnricher enricher;

    public KnownSiteIngestionStrategy(
            SourceDocumentLoader documents, KnownSiteParsers parsers, ListingEnricher enricher) {
        this.documents = documents;
        this.parsers = parsers;
        this.enricher = enricher;
    }

    @Override
    public SourceStrategyKind kind() {
        return SourceStrategyKind.KNOWN_SITE;
    }

    @Override
    public Mono<List<CandidatePost>> ingest(SourceDefinition source) {
        KnownSiteParser parser = parsers.resolve(source.options().siteKey());
        String listingUrl = valueOr(source.options().listingUrl(), parser.defaultListingUrl());
        return documents
                .load(listingUrl)
                .publishOn(Schedulers.boundedElastic())
                .map(parser::parseListing)
                .flatMap(items -> items.isEmpty()
                        ? Mono.error(new SourceIngestionException(
                                "No known-site posts found using parser '" + parser.key() + "'"))
                        : enricher.enrich(listingUrl, RecentCandidates.listings(items, source.lastSuccessAt())));
    }

    private static String valueOr(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }
}
