package com.goodnews.backendjava.ingestion.strategy;

import com.goodnews.backendjava.ingestion.application.SourceIngestionException;
import com.goodnews.backendjava.ingestion.application.port.SourceDocumentLoader;
import com.goodnews.backendjava.ingestion.model.CandidatePost;
import com.goodnews.backendjava.ingestion.model.ListingCandidate;
import com.goodnews.backendjava.ingestion.parsing.ArticleContentParser;
import java.net.URI;
import java.time.Instant;
import java.util.List;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

@Component
final class ListingEnricher {
    private final SourceDocumentLoader documents;
    private final ArticleContentParser articles;

    ListingEnricher(SourceDocumentLoader documents, ArticleContentParser articles) {
        this.documents = documents;
        this.articles = articles;
    }

    Mono<List<CandidatePost>> enrich(String listingUrl, List<ListingCandidate> items) {
        return Flux.fromIterable(items)
                .concatMap(item -> enrichOne(listingUrl, item))
                .collectList()
                .onErrorMap(
                        IllegalArgumentException.class,
                        error -> new SourceIngestionException("Invalid article URL", error));
    }

    private Mono<CandidatePost> enrichOne(String listingUrl, ListingCandidate item) {
        String articleUrl = URI.create(listingUrl).resolve(item.href()).toString();
        if (item.rawContent() != null) {
            return documents
                    .validate(articleUrl)
                    .thenReturn(new CandidatePost(
                            articleUrl,
                            item.title(),
                            item.publishedAt(),
                            item.rawContent(),
                            item.publicationDateSource()));
        }
        return documents
                .load(articleUrl)
                .publishOn(Schedulers.boundedElastic())
                .map(html -> articles.parse(html, item.title()))
                .map(article -> {
                    Instant published = article.publishedAt() == null ? item.publishedAt() : article.publishedAt();
                    var source = article.publishedAt() == null
                            ? item.publicationDateSource()
                            : article.publicationDateSource();
                    return new CandidatePost(articleUrl, item.title(), published, article.rawContent(), source);
                });
    }
}
