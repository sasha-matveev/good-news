package com.goodnews.backendjava.analysis.infrastructure.gemini;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.goodnews.backendjava.analysis.model.AnalysisContext;
import com.goodnews.backendjava.analysis.model.AnalysisRequest;
import java.io.IOException;
import java.time.Duration;
import java.util.List;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.mockwebserver.RecordedRequest;
import okhttp3.mockwebserver.SocketPolicy;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.test.StepVerifier;

class GeminiAnalysisClientTest {
    private final ObjectMapper objectMapper = new ObjectMapper();
    private MockWebServer server;

    @BeforeEach
    void startServer() throws IOException {
        server = new MockWebServer();
        server.start();
    }

    @AfterEach
    void stopServer() throws IOException {
        server.shutdown();
    }

    @Test
    void sendsConfiguredRequestAndNormalizesSuccessfulBatch() throws Exception {
        server.enqueue(
                jsonCandidate(
                        """
                {"results":[{"id":"1","summary_ru":"Русское резюме.","topics":["Java"],
                "format":"tutorial","technical_depth":"advanced","verdict":"interesting",
                "verdict_reason":"Useful article.","relevance_score":8}]}
                """));
        GeminiAnalysisClient client = client(1);
        String content = "x".repeat(5000);

        StepVerifier.create(client.analyze(List.of(new AnalysisRequest(1, "Title", content)), context()))
                .assertNext(results -> {
                    assertThat(results).hasSize(1);
                    assertThat(results.getFirst().relevanceScore()).isEqualTo(8);
                })
                .verifyComplete();

        RecordedRequest request = server.takeRequest();
        assertThat(request.getPath()).isEqualTo("/models/test-model:generateContent");
        assertThat(request.getHeader("x-goog-api-key")).isEqualTo("test-key");
        String body = request.getBody().readUtf8();
        assertThat(body)
                .contains(
                        "Title",
                        "summary instructions",
                        "reader profile",
                        "x".repeat(4000),
                        "10 = a perfect match",
                        "0 = irrelevant",
                        "Judge for THIS reader",
                        "When no profile is given",
                        "general value to a software developer");
        assertThat(body).doesNotContain("x".repeat(4001));
    }

    @Test
    void retriesOnly429UsingRetryAfterAndExhaustsConfiguredAttempts() {
        server.enqueue(new MockResponse().setResponseCode(429).addHeader("Retry-After", "0"));
        server.enqueue(jsonCandidate("{\"results\":[]}"));
        StepVerifier.create(client(2).analyze(List.of(request()), context()))
                .assertNext(results -> assertThat(results).isEmpty())
                .verifyComplete();
        assertThat(server.getRequestCount()).isEqualTo(2);

        server.enqueue(new MockResponse().setResponseCode(429).addHeader("Retry-After", "0"));
        server.enqueue(new MockResponse().setResponseCode(429).addHeader("Retry-After", "0"));
        StepVerifier.create(client(2).analyze(List.of(request()), context()))
                .expectErrorSatisfies(error -> assertThat(error)
                        .isInstanceOf(GeminiAnalysisClient.GeminiHttpException.class)
                        .hasMessageContaining("429"))
                .verify();
        assertThat(server.getRequestCount()).isEqualTo(4);
    }

    @Test
    void permanentFailureAndMalformedCandidateAreNotRetried() {
        server.enqueue(new MockResponse().setResponseCode(500).setBody("failure"));
        StepVerifier.create(client(4).analyze(List.of(request()), context()))
                .expectErrorSatisfies(error -> assertThat(error).hasMessageContaining("500"))
                .verify();
        assertThat(server.getRequestCount()).isEqualTo(1);

        server.enqueue(
                new MockResponse().setHeader("Content-Type", "application/json").setBody("{}"));
        StepVerifier.create(client(4).analyze(List.of(request()), context()))
                .expectErrorSatisfies(error -> assertThat(error).hasMessageContaining("missing candidate text"))
                .verify();
        assertThat(server.getRequestCount()).isEqualTo(2);
    }

    @Test
    void lastValidDuplicateWinsAndMissingItemsAreAbsent() {
        String item =
                """
                {"id":1,"summary_ru":"Резюме.","topics":[],"format":"news",
                "technical_depth":"beginner","verdict":"interesting","verdict_reason":"Useful."}
                """;
        String last = item.replace("\"verdict_reason\":\"Useful.\"", "\"verdict_reason\":\"Last wins.\"");
        server.enqueue(jsonCandidate("{\"results\":[" + item + "," + last + "]}"));

        StepVerifier.create(client(1).analyze(List.of(request(), new AnalysisRequest(2, "Two", "Body")), context()))
                .assertNext(results -> {
                    assertThat(results).hasSize(1);
                    assertThat(results.getFirst().postId()).isEqualTo(1);
                    assertThat(results.getFirst().verdictReason()).isEqualTo("Last wins.");
                })
                .verifyComplete();
    }

    @Test
    void acceptsIntegralNumericIdAndRejectsNonIntegralBooleanAndContainerIds() {
        server.enqueue(jsonCandidate("{\"results\":[" + validItem("1.0") + "," + validItem("2.5") + ","
                + validItem("true") + "," + validItem("{}") + "]}"));

        StepVerifier.create(client(1).analyze(List.of(request(), new AnalysisRequest(2, "Two", "Body")), context()))
                .assertNext(results -> assertThat(results)
                        .extracting(result -> result.postId())
                        .containsExactly(1L))
                .verifyComplete();
    }

    @Test
    void appliesLocalizedResponseTimeoutWithoutWaitingSixtySeconds() {
        server.enqueue(new MockResponse().setSocketPolicy(SocketPolicy.NO_RESPONSE));
        GeminiAnalysisClient timeoutClient = new GeminiAnalysisClient(
                WebClient.builder(),
                objectMapper,
                new ReactiveRequestRateLimiter(Integer.MAX_VALUE),
                "test-key",
                "test-model",
                1,
                server.url("/").toString().replaceAll("/$", ""),
                Duration.ofMillis(50));

        StepVerifier.create(timeoutClient.analyze(List.of(request()), context()))
                .expectError()
                .verify(Duration.ofSeconds(3));
    }

    private String validItem(String id) {
        return "{\"id\":" + id
                + ",\"summary_ru\":\"\\u0420\\u0435\\u0437\\u044e\\u043c\\u0435.\",\"topics\":[],"
                + "\"format\":\"news\",\"technical_depth\":\"beginner\",\"verdict\":\"interesting\","
                + "\"verdict_reason\":\"Useful.\"}";
    }

    private GeminiAnalysisClient client(int attempts) {
        return new GeminiAnalysisClient(
                WebClient.builder(),
                objectMapper,
                new ReactiveRequestRateLimiter(Integer.MAX_VALUE),
                "test-key",
                "test-model",
                attempts,
                server.url("/").toString().replaceAll("/$", ""));
    }

    private MockResponse jsonCandidate(String candidateText) {
        return new MockResponse()
                .setHeader("Content-Type", "application/json")
                .setBody(objectMapper
                        .createObjectNode()
                        .set(
                                "candidates",
                                objectMapper
                                        .createArrayNode()
                                        .add(objectMapper
                                                .createObjectNode()
                                                .set(
                                                        "content",
                                                        objectMapper
                                                                .createObjectNode()
                                                                .set(
                                                                        "parts",
                                                                        objectMapper
                                                                                .createArrayNode()
                                                                                .add(objectMapper
                                                                                        .createObjectNode()
                                                                                        .put("text", candidateText))))))
                        .toString());
    }

    private AnalysisRequest request() {
        return new AnalysisRequest(1, "One", "Body");
    }

    private AnalysisContext context() {
        return new AnalysisContext("summary instructions", "reason instructions", "reader profile");
    }
}
