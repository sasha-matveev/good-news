package com.goodnews.backendjava.ingestion.strategy;

import static org.assertj.core.api.Assertions.assertThat;

import com.goodnews.backendjava.ingestion.application.port.SourceDocumentLoader;
import com.goodnews.backendjava.ingestion.model.ListingCandidate;
import com.goodnews.backendjava.ingestion.model.PublicationDateSource;
import com.goodnews.backendjava.ingestion.parsing.ArticleContentParser;
import com.goodnews.backendjava.ingestion.parsing.PublicationDateParser;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Mono;
import tools.jackson.databind.ObjectMapper;

class ListingEnricherTest {
    @Test
    void resolvesReferencesAgainstOriginalListingUri() {
        RecordingDocuments documents = new RecordingDocuments();
        ListingEnricher enricher = new ListingEnricher(
                documents, new ArticleContentParser(new ObjectMapper(), new PublicationDateParser()));
        List<ListingCandidate> candidates =
                List.of(candidate("post"), candidate("/root"), candidate("https://other.example/absolute"));

        enricher.enrich("https://example.com/news", candidates).block();

        assertThat(documents.validated)
                .containsExactly(
                        "https://example.com/post", "https://example.com/root", "https://other.example/absolute");
    }

    @Test
    void trailingSlashPreservesListingDirectory() {
        RecordingDocuments documents = new RecordingDocuments();
        ListingEnricher enricher = new ListingEnricher(
                documents, new ArticleContentParser(new ObjectMapper(), new PublicationDateParser()));

        enricher.enrich("https://example.com/news/", List.of(candidate("post"))).block();

        assertThat(documents.validated).containsExactly("https://example.com/news/post");
    }

    private static ListingCandidate candidate(String href) {
        return new ListingCandidate(href, "Title", null, PublicationDateSource.NONE, "summary");
    }

    private static final class RecordingDocuments implements SourceDocumentLoader {
        private final List<String> validated = new ArrayList<>();

        @Override
        public Mono<String> load(String url) {
            return Mono.error(new AssertionError("Unexpected article load"));
        }

        @Override
        public Mono<Void> validate(String url) {
            validated.add(url);
            return Mono.empty();
        }
    }
}
