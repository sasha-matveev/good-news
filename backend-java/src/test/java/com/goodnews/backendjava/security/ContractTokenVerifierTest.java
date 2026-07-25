package com.goodnews.backendjava.security;

import static org.assertj.core.api.Assertions.assertThat;

import com.goodnews.backendjava.config.AppProperties;
import com.goodnews.backendjava.config.AuthProperties;
import com.goodnews.backendjava.config.DatabaseProperties;
import com.goodnews.backendjava.config.EmailProperties;
import com.goodnews.backendjava.config.GeminiProperties;
import com.goodnews.backendjava.config.GoodNewsProperties;
import com.goodnews.backendjava.config.ObservabilityProperties;
import com.goodnews.backendjava.config.SchedulerProperties;
import org.junit.jupiter.api.Test;
import reactor.test.StepVerifier;

class ContractTokenVerifierTest {

    @Test
    void deterministicVerifierIsAvailableOnlyInContractEnvironment() {
        GoodNewsProperties properties = properties(
                "contract",
                """
                {"allowed":{"email":"reader@example.com","email_verified":true}}
                """);
        FirebaseTokenVerifier verifier = new JwtTokenVerifierConfiguration().firebaseTokenVerifier(properties);

        StepVerifier.create(verifier.verify("allowed"))
                .assertNext(claims -> {
                    assertThat(claims.email()).isEqualTo("reader@example.com");
                    assertThat(claims.emailVerified()).isTrue();
                })
                .verifyComplete();
        StepVerifier.create(verifier.verify("missing"))
                .expectErrorMatches(error -> error.getMessage().contains("Unknown contract token"))
                .verify();
    }

    private GoodNewsProperties properties(String environment, String tokens) {
        return new GoodNewsProperties(
                new AppProperties(
                        environment,
                        "localhost",
                        8000,
                        5173,
                        "localhost",
                        8100,
                        "localhost",
                        8200,
                        "localhost",
                        8300,
                        null,
                        null,
                        null,
                        tokens),
                new DatabaseProperties(null, "localhost", 5432, "good_news", "good_news", null),
                new AuthProperties("contract-project", "reader@example.com", null),
                new SchedulerProperties(30, 3, null),
                new GeminiProperties(null, "gemini-3.1-flash-lite", 10, 8, 4),
                new EmailProperties(null, null, null),
                new ObservabilityProperties(null, "127.0.0.1", 3000, "18:00"));
    }
}
