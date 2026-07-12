package com.goodnews.backendjava.security;

import static org.mockito.BDDMockito.given;

import com.goodnews.backendjava.api.dto.InternalJobDtos;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.AutoConfigureWebTestClient;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        classes = {
            com.goodnews.backendjava.BackendJavaApplication.class,
            ReactiveSecurityIntegrationTest.SecurityTestController.class
        })
@AutoConfigureWebTestClient
@TestPropertySource(
        properties = {
            "spring.flyway.enabled=false",
            "good-news.auth.firebase-project-id=good-news-test",
            "good-news.auth.allowed-emails=owner@example.com",
            "good-news.scheduler.invoker=scheduler@test.iam.gserviceaccount.com",
            "good-news.auth.oidc-audience=https://good-news-jobs.example"
        })
class ReactiveSecurityIntegrationTest {

    @Autowired
    private WebTestClient webTestClient;

    @MockBean
    private FirebaseTokenVerifier firebaseTokenVerifier;

    @MockBean
    private GoogleOidcTokenVerifier googleOidcTokenVerifier;

    @Test
    void apiRequiresBearerTokenWhenFirebaseAuthConfigured() {
        webTestClient
                .get()
                .uri("/api/test/posts")
                .exchange()
                .expectStatus()
                .isUnauthorized()
                .expectBody()
                .jsonPath("$.detail")
                .isEqualTo("Missing bearer token.");
    }

    @Test
    void apiHealthStaysPublic() {
        webTestClient
                .get()
                .uri("/api/health")
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .jsonPath("$.status")
                .isEqualTo("ok");
    }

    @Test
    void apiRejectsNonAllowlistedEmail() {
        given(firebaseTokenVerifier.verify("stranger"))
                .willReturn(Mono.just(new TokenClaims("stranger@example.com", true)));

        webTestClient
                .get()
                .uri("/api/test/posts")
                .header("Authorization", "Bearer stranger")
                .exchange()
                .expectStatus()
                .isForbidden()
                .expectBody()
                .jsonPath("$.detail")
                .isEqualTo("Not allowed.");
    }

    @Test
    void apiAcceptsAllowlistedVerifiedEmail() {
        given(firebaseTokenVerifier.verify("owner")).willReturn(Mono.just(new TokenClaims("owner@example.com", true)));

        webTestClient
                .get()
                .uri("/api/test/posts")
                .header("Authorization", "Bearer owner")
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .jsonPath("$.status")
                .isEqualTo("ok");
    }

    @Test
    void internalJobRequiresOidcToken() {
        webTestClient
                .post()
                .uri("/internal/jobs/test")
                .exchange()
                .expectStatus()
                .isUnauthorized()
                .expectBody()
                .jsonPath("$.detail")
                .isEqualTo("Missing bearer token.");
    }

    @Test
    void internalJobRejectsWrongServiceAccount() {
        given(googleOidcTokenVerifier.verify("intruder"))
                .willReturn(Mono.just(new TokenClaims("intruder@test.iam.gserviceaccount.com", true)));

        webTestClient
                .post()
                .uri("/internal/jobs/test")
                .header("Authorization", "Bearer intruder")
                .exchange()
                .expectStatus()
                .isForbidden()
                .expectBody()
                .jsonPath("$.detail")
                .isEqualTo("Not allowed.");
    }

    @Test
    void internalJobRunsForSchedulerServiceAccount() {
        given(googleOidcTokenVerifier.verify("scheduler"))
                .willReturn(Mono.just(new TokenClaims("scheduler@test.iam.gserviceaccount.com", true)));

        webTestClient
                .post()
                .uri("/internal/jobs/test")
                .header("Authorization", "Bearer scheduler")
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .jsonPath("$.processed_source_ids[0]")
                .isEqualTo(1)
                .jsonPath("$.analyzed_pending")
                .isEqualTo(true);
    }

    @Test
    void internalJobOptionsPreflightBypassesSchedulerAuth() {
        webTestClient
                .options()
                .uri("/internal/jobs/test")
                .exchange()
                .expectStatus()
                .isOk();
    }

    @RestController
    static class SecurityTestController {

        @GetMapping("/api/test/posts")
        Mono<StatusResponse> posts() {
            return Mono.just(new StatusResponse("ok"));
        }

        @PostMapping("/internal/jobs/test")
        Mono<InternalJobDtos.SourceSyncJobResponse> jobs() {
            return Mono.just(new InternalJobDtos.SourceSyncJobResponse(List.of(1L), true));
        }
    }

    record StatusResponse(String status) {}
}
