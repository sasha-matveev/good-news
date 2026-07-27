package com.goodnews.backendjava.digest;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

import com.goodnews.backendjava.config.EmailProperties;
import com.goodnews.backendjava.config.GoodNewsProperties;
import com.goodnews.backendjava.service.PostService;
import java.time.Instant;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.transaction.reactive.TransactionalOperator;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;
import tools.jackson.databind.ObjectMapper;

@ExtendWith(MockitoExtension.class)
class DigestGenerationServiceTest {
    @Mock
    PostService posts;

    @Mock
    DigestRepository digests;

    @Mock
    DigestEmailRenderer renderer;

    @Mock
    GoodNewsProperties properties;

    @Mock
    TransactionalOperator transactions;

    private DigestGenerationService service;

    @BeforeEach
    void setUp() {
        when(properties.email()).thenReturn(new EmailProperties(null, null, null));
        when(transactions.transactional(any(Mono.class))).thenAnswer(invocation -> invocation.getArgument(0));
        service = new DigestGenerationService(posts, digests, renderer, properties, new ObjectMapper(), transactions);
    }

    @Test
    void invalidOriginIsReportedThroughPublisherInsteadOfSynchronousThrow() {
        Mono<GeneratedDigest> result = service.generateDaily(Instant.parse("2026-07-17T12:00:00Z"));

        assertThatCode(() -> service.generateWeekly(Instant.parse("2026-07-17T12:00:00Z")))
                .doesNotThrowAnyException();
        StepVerifier.create(result)
                .expectErrorMessage("Invalid public origin contract GOOD_NEWS_PUBLIC_FRONTEND_ORIGIN")
                .verify();
    }

    @Test
    void rejectsNonWebContentApiOrigin() {
        when(properties.email())
                .thenReturn(new EmailProperties(null, "javascript:alert(1)", "https://good-news.example"));

        StepVerifier.create(service.generateDaily(Instant.parse("2026-07-17T12:00:00Z")))
                .expectErrorMessage("Invalid public origin contract GOOD_NEWS_PUBLIC_CONTENT_API_ORIGIN")
                .verify();
    }
}
