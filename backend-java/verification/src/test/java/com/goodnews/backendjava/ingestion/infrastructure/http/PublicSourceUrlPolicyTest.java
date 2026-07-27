package com.goodnews.backendjava.ingestion.infrastructure.http;

import static org.assertj.core.api.Assertions.assertThat;

import com.goodnews.backendjava.ingestion.application.SourceIngestionException;
import org.junit.jupiter.api.Test;
import reactor.test.StepVerifier;

class PublicSourceUrlPolicyTest {
    private final PublicSourceUrlPolicy policy = new PublicSourceUrlPolicy();

    @Test
    void rejectsNonHttpAndLocalDestinations() {
        StepVerifier.create(policy.validate("file:///etc/passwd"))
                .expectError(SourceIngestionException.class)
                .verify();
        StepVerifier.create(policy.validate("http://127.0.0.1/latest/meta-data"))
                .expectError(SourceIngestionException.class)
                .verify();
        StepVerifier.create(policy.validate("http://169.254.169.254/latest/meta-data"))
                .expectError(SourceIngestionException.class)
                .verify();
        StepVerifier.create(policy.validate("http://192.0.2.1/documentation"))
                .expectError(SourceIngestionException.class)
                .verify();
        StepVerifier.create(policy.validate("http://[2001:db8::1]/documentation"))
                .expectError(SourceIngestionException.class)
                .verify();
    }

    @Test
    void acceptsPublicHttpDestination() {
        for (String url : java.util.List.of(
                "https://example.com/feed",
                "http://192.1.255.1/feed",
                "http://198.20.0.1/feed",
                "http://203.0.112.1/feed",
                "http://[2001:db9::1]/feed")) {
            StepVerifier.create(policy.validate(url))
                    .assertNext(
                            validated -> assertThat(validated.uri().getScheme()).isIn("http", "https"))
                    .verifyComplete();
        }
    }
}
