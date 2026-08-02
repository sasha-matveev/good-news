package com.goodnews.backendjava.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verifyNoInteractions;

import com.goodnews.backendjava.api.dto.InternalJobDtos;
import com.goodnews.backendjava.config.ReactiveDatabaseSmokeProbe;
import com.goodnews.backendjava.jobs.ScheduledDigestJobs;
import com.goodnews.backendjava.jobs.SourceSyncJob;
import java.time.Instant;
import java.util.List;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.boot.webtestclient.autoconfigure.AutoConfigureWebTestClient;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.reactive.result.method.annotation.RequestMappingHandlerMapping;
import org.springframework.web.util.pattern.PathPattern;
import reactor.core.publisher.Mono;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        classes = {
            com.goodnews.backendjava.GoodNewsApplication.class,
            ReactiveSecurityIntegrationTest.SecurityTestController.class
        })
@AutoConfigureWebTestClient
@TestPropertySource(
        properties = {
            "good-news.auth.firebase-project-id=good-news-test",
            "good-news.auth.allowed-emails=owner@example.com",
            "good-news.scheduler.invoker=scheduler@test.iam.gserviceaccount.com",
            "good-news.auth.oidc-audience=https://good-news-jobs.example",
            "good-news.email.public-frontend-origin=https://good-news.example"
        })
class ReactiveSecurityIntegrationTest {

    private static final Set<RequestMethod> SAFE_METHODS =
            Set.of(RequestMethod.GET, RequestMethod.HEAD, RequestMethod.OPTIONS, RequestMethod.TRACE);

    @Autowired
    private WebTestClient webTestClient;

    @LocalServerPort
    private int port;

    @MockitoBean
    private FirebaseTokenVerifier firebaseTokenVerifier;

    @MockitoBean
    private GoogleOidcTokenVerifier googleOidcTokenVerifier;

    @MockitoBean
    private SourceSyncJob sourceSyncJob;

    @MockitoBean
    private ScheduledDigestJobs scheduledDigestJobs;

    @MockitoBean
    private ReactiveDatabaseSmokeProbe databaseSmokeProbe;

    @Autowired
    @Qualifier("requestMappingHandlerMapping")
    private RequestMappingHandlerMapping requestMappings;

    @Test
    void stateChangingControllersUseBearerProtectedNamespaces() {
        Set<String> unprotected = requestMappings.getHandlerMethods().entrySet().stream()
                .filter(entry ->
                        entry.getValue().getBeanType().getPackageName().startsWith("com.goodnews.backendjava.api"))
                .filter(entry ->
                        entry.getKey().getMethodsCondition().getMethods().isEmpty()
                                || entry.getKey().getMethodsCondition().getMethods().stream()
                                        .anyMatch(method -> !SAFE_METHODS.contains(method)))
                .flatMap(entry -> entry.getKey().getPatternsCondition().getPatterns().stream())
                .map(PathPattern::getPatternString)
                .filter(path -> !path.startsWith("/api/") && !path.startsWith("/internal/jobs/"))
                .collect(java.util.stream.Collectors.toUnmodifiableSet());

        assertThat(unprotected).isEmpty();
    }

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
        given(databaseSmokeProbe.verifyRequiredSchema()).willReturn(Mono.just(true));

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

        serverWebTestClient()
                .get()
                .uri("/api/test/posts")
                .header("Authorization", "Bearer owner")
                .header("Origin", "https://good-news.example")
                .exchange()
                .expectStatus()
                .isOk()
                .expectHeader()
                .valueEquals("Access-Control-Allow-Origin", "https://good-news.example")
                .expectHeader()
                .valueEquals("X-Good-News-Backend", "java")
                .expectBody()
                .jsonPath("$.status")
                .isEqualTo("ok");
    }

    @Test
    void apiCookieOnlyMutationCannotAuthenticate() {
        webTestClient
                .post()
                .uri("/api/test/posts")
                .cookie("SESSION", "browser-ambient-credential")
                .header("Origin", "https://good-news.example")
                .exchange()
                .expectStatus()
                .isForbidden();

        verifyNoInteractions(firebaseTokenVerifier);
    }

    @Test
    void apiBearerMutationRemainsStatelessWithBrowserCookies() {
        given(firebaseTokenVerifier.verify("owner")).willReturn(Mono.just(new TokenClaims("owner@example.com", true)));

        webTestClient
                .post()
                .uri("/api/test/posts")
                .header("Authorization", "Bearer owner")
                .cookie("SESSION", "unrelated-browser-cookie")
                .exchange()
                .expectStatus()
                .isOk()
                .expectHeader()
                .doesNotExist("Set-Cookie")
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
    void internalJobCookieOnlyMutationCannotAuthenticate() {
        webTestClient
                .post()
                .uri("/internal/jobs/test")
                .cookie("SESSION", "browser-ambient-credential")
                .header("Origin", "https://good-news.example")
                .exchange()
                .expectStatus()
                .isForbidden();

        verifyNoInteractions(googleOidcTokenVerifier);
    }

    @Test
    void realSourceSyncEndpointRequiresOidcToken() {
        webTestClient
                .post()
                .uri("/internal/jobs/source-sync")
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
    void realDigestEndpointRunsForSchedulerServiceAccount() {
        given(googleOidcTokenVerifier.verify("scheduler"))
                .willReturn(Mono.just(new TokenClaims("scheduler@test.iam.gserviceaccount.com", true)));
        given(scheduledDigestJobs.runDue(org.mockito.ArgumentMatchers.any(Instant.class)))
                .willReturn(Mono.just(new ScheduledDigestJobs.RunResult(null, null, List.of())));

        webTestClient
                .post()
                .uri("/internal/jobs/digests")
                .header("Authorization", "Bearer scheduler")
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .json("{\"daily_ran_for\":null,\"weekly_ran_for\":null,\"errors\":[]}");
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

    @Test
    void browserPreflightAllowsAuthorizationAndCorrelationHeaders() {
        serverWebTestClient()
                .options()
                .uri("/api/test/posts")
                .header("Origin", "https://good-news.example")
                .header("Access-Control-Request-Method", "GET")
                .header("Access-Control-Request-Headers", "authorization,x-correlation-id")
                .exchange()
                .expectStatus()
                .isOk()
                .expectHeader()
                .valueEquals("Access-Control-Allow-Origin", "https://good-news.example")
                .expectHeader()
                .valueEquals("X-Good-News-Backend", "java");
    }

    private WebTestClient serverWebTestClient() {
        return WebTestClient.bindToServer().baseUrl("http://localhost:" + port).build();
    }

    @RestController
    static class SecurityTestController {

        @GetMapping("/api/test/posts")
        Mono<StatusResponse> posts() {
            return Mono.just(new StatusResponse("ok"));
        }

        @PostMapping("/api/test/posts")
        Mono<StatusResponse> updatePosts() {
            return Mono.just(new StatusResponse("ok"));
        }

        @PostMapping("/internal/jobs/test")
        Mono<InternalJobDtos.SourceSyncJobResponse> jobs() {
            return Mono.just(new InternalJobDtos.SourceSyncJobResponse(List.of(1L), true));
        }
    }

    record StatusResponse(String status) {}
}
