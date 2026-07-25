package com.goodnews.backendjava.ingestion.infrastructure.http;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import reactor.test.StepVerifier;

class StubSourceDocumentLoaderTest {

    @Test
    void returnsOnlyConfiguredDeterministicDocuments() {
        StubSourceDocumentLoader loader =
                new StubSourceDocumentLoader("{\"https://example.test/feed\":\"<rss/>\"}", new ObjectMapper());

        StepVerifier.create(loader.load("https://example.test/feed"))
                .expectNext("<rss/>")
                .verifyComplete();
        StepVerifier.create(loader.load("https://missing.test/feed"))
                .expectErrorMessage("No deterministic response for source URL")
                .verify();
    }
}
