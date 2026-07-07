package com.goodnews.backendjava.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.AutoConfigureWebTestClient;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@AutoConfigureWebTestClient
@Testcontainers(disabledWithoutDocker = true)
class FeedFeedbackWantToReadApiTest {

    @Container
    static final PostgreSQLContainer<?> POSTGRESQL = new PostgreSQLContainer<>("postgres:16-alpine")
        .withDatabaseName("good_news")
        .withUsername("good_news")
        .withPassword("good-news-secret");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("good-news.database.postgres-host", POSTGRESQL::getHost);
        registry.add("good-news.database.postgres-port", POSTGRESQL::getFirstMappedPort);
        registry.add("good-news.database.postgres-database", POSTGRESQL::getDatabaseName);
        registry.add("good-news.database.postgres-user", POSTGRESQL::getUsername);
        registry.add("good-news.database.postgres-password", POSTGRESQL::getPassword);
        registry.add("good-news.email.public-frontend-origin", () -> "https://good-news.example");
    }

    @Autowired
    private WebTestClient webTestClient;

    @Autowired
    private DatabaseClient databaseClient;

    @Autowired
    private ObjectMapper objectMapper;

    @BeforeEach
    void cleanDatabase() {
        databaseClient.sql("TRUNCATE TABLE read_later, post_analysis, feedback, posts, sources RESTART IDENTITY CASCADE")
            .then()
            .block();
    }

    @Test
    void getPostsDefaultsToLastMonthAndReturnsRankingExplanation() {
        insertSource(1, "Alpha");
        insertSource(2, "Beta");
        insertPost(1, 1, "https://alpha.example/posts/older", "Older", utc("2026-03-01T08:00:00Z"), "Too old for the default window.");
        insertPost(2, 2, "https://beta.example/posts/newer", "Newer", utc("2026-04-20T09:00:00Z"), "Fresh enough for the default window.");

        webTestClient.get()
            .uri("/api/posts")
            .exchange()
            .expectStatus().isOk()
            .expectBody()
            .json("""
                [{
                  "id": 2,
                  "source_id": 2,
                  "source_name": "Beta",
                  "canonical_url": "https://beta.example/posts/newer",
                  "title": "Newer",
                  "published_at": "2026-04-20T09:00:00Z",
                  "published_at_source": null,
                  "raw_content": "Fresh enough for the default window.",
                  "feedback_state": null,
                  "read_later": false,
                  "summary_ru": null,
                  "verdict": null,
                  "verdict_reason": null,
                  "relevance_score": null,
                  "ranking_explanation": "feedback=none; source_affinity=0.0; topic_affinity=0.0; format_affinity=0.0; practical=0.1; depth=0.0; recency=0.3"
                }]
                """);
    }

    @Test
    void getPostsSupportsFilteringSortingAndPagination() throws Exception {
        insertSource(1, "Alpha");
        insertPost(1, 1, "https://alpha.example/posts/one", "Older but high relevance", utc("2026-01-01T08:00:00Z"), "Older content.");
        insertPost(2, 1, "https://alpha.example/posts/two", "Newer but low relevance", utc("2026-04-25T08:00:00Z"), "Newer content.");
        insertPost(3, 1, "https://alpha.example/posts/three", "Untouched", utc("2026-04-26T08:00:00Z"), "No feedback yet.");
        insertFeedback(1, "interesting");
        insertFeedback(3, "norm");
        insertAnalysis(1, "s1", Map.of(
            "topics", new String[] { "devops" },
            "format", "guide",
            "technical_depth", "medium",
            "verdict", "interesting",
            "verdict_reason", "Relevant.",
            "relevance_score", 9
        ));
        insertAnalysis(2, "s2", Map.of(
            "topics", new String[] { "devops" },
            "format", "guide",
            "technical_depth", "medium",
            "verdict", "interesting",
            "verdict_reason", "Relevant.",
            "relevance_score", 3
        ));
        insertReadLater(2);

        webTestClient.get()
            .uri("/api/posts?sort=match&window=all&limit=2")
            .exchange()
            .expectStatus().isOk()
            .expectBody()
            .jsonPath("$[0].id").isEqualTo(1)
            .jsonPath("$[1].id").isEqualTo(2);

        webTestClient.get()
            .uri("/api/posts?sort=date&window=all&limit=2&offset=1")
            .exchange()
            .expectStatus().isOk()
            .expectBody()
            .jsonPath("$[0].id").isEqualTo(2)
            .jsonPath("$[1].id").isEqualTo(1);

        webTestClient.get()
            .uri("/api/posts?window=all&feedback_state=none")
            .exchange()
            .expectStatus().isOk()
            .expectBody()
            .jsonPath("$[0].id").isEqualTo(2);

        webTestClient.get()
            .uri("/api/posts?window=all&read_later=true")
            .exchange()
            .expectStatus().isOk()
            .expectBody()
            .jsonPath("$[0].id").isEqualTo(2);
    }

    @Test
    void postReadLaterIsIdempotentAndIndependentFromFeedback() {
        insertSource(1, "Alpha");
        insertPost(1, 1, "https://alpha.example/posts/one", "Alpha One", utc("2026-04-20T09:00:00Z"), "Fresh content.");
        insertFeedback(1, "interesting");

        webTestClient.post()
            .uri("/api/posts/1/read-later")
            .bodyValue(Map.of("saved", true))
            .exchange()
            .expectStatus().isOk()
            .expectBody()
            .json("{\"post_id\":1,\"read_later\":true}");

        webTestClient.post()
            .uri("/api/posts/1/read-later")
            .bodyValue(Map.of("saved", true))
            .exchange()
            .expectStatus().isOk();

        webTestClient.get()
            .uri("/api/posts?window=all&read_later=true")
            .exchange()
            .expectStatus().isOk()
            .expectBody()
            .jsonPath("$[0].feedback_state").isEqualTo("interesting");

        webTestClient.post()
            .uri("/api/posts/1/read-later")
            .bodyValue(Map.of("saved", false))
            .exchange()
            .expectStatus().isOk()
            .expectBody()
            .json("{\"post_id\":1,\"read_later\":false}");
    }

    @Test
    void postReadLaterAndOpenReturn404ForMissingPost() {
        webTestClient.post()
            .uri("/api/posts/999/read-later")
            .bodyValue(Map.of("saved", true))
            .exchange()
            .expectStatus().isNotFound()
            .expectBody()
            .jsonPath("$.detail").isEqualTo("Post not found");

        webTestClient.post()
            .uri("/api/posts/999/open")
            .exchange()
            .expectStatus().isNotFound()
            .expectBody()
            .jsonPath("$.detail").isEqualTo("Post not found");
    }

    @Test
    void feedbackApisPreserveUpsertAndDigestRedirectContract() {
        insertSource(1, "Alpha");
        insertPost(1, 1, "https://alpha.example/posts/one", "Alpha One", utc("2026-04-20T09:00:00Z"), "Fresh content.");

        webTestClient.put()
            .uri("/api/feedback/1")
            .bodyValue(Map.of("state", "interesting"))
            .exchange()
            .expectStatus().isOk()
            .expectBody()
            .json("{\"post_id\":1,\"state\":\"interesting\"}");

        webTestClient.get()
            .uri("/api/feedback/1/want_to_read?digest_id=21")
            .exchange()
            .expectStatus().isTemporaryRedirect()
            .expectHeader().location("https://good-news.example/want-to-read?digest_id=21&feedback=want_to_read&from=digest_email&post_id=1");

        webTestClient.get()
            .uri("/api/posts?window=all&read_later=true")
            .exchange()
            .expectStatus().isOk()
            .expectBody()
            .jsonPath("$[0].id").isEqualTo(1);

        webTestClient.get()
            .uri("/api/feedback/1/interesting?digest_id=22")
            .exchange()
            .expectStatus().isTemporaryRedirect()
            .expectHeader().location("https://good-news.example/digests?digest_id=22&feedback=interesting&from=digest_email&post_id=1");
    }

    @Test
    void wantToReadApiPreservesStateTransitions() {
        insertSource(1, "Alpha");
        insertPost(1, 1, "https://alpha.example/posts/one", "Alpha One", utc("2026-04-20T09:00:00Z"), "Fresh content.");

        webTestClient.put()
            .uri("/api/want-to-read/1")
            .bodyValue(Map.of("saved", true))
            .exchange()
            .expectStatus().isOk()
            .expectBody()
            .json("{\"post_id\":1,\"saved\":true,\"feedback_state\":\"want_to_read\"}");

        webTestClient.put()
            .uri("/api/want-to-read/1")
            .bodyValue(Map.of("saved", false))
            .exchange()
            .expectStatus().isOk()
            .expectBody()
            .json("{\"post_id\":1,\"saved\":false,\"feedback_state\":null}");

        insertFeedback(1, "interesting");

        webTestClient.put()
            .uri("/api/want-to-read/1")
            .bodyValue(Map.of("saved", false))
            .exchange()
            .expectStatus().isOk()
            .expectBody()
            .json("{\"post_id\":1,\"saved\":false,\"feedback_state\":\"interesting\"}");
    }

    private void insertSource(long id, String displayName) {
        databaseClient.sql("""
                INSERT INTO sources (id, original_url, display_name, strategy_kind, active, status, created_at, updated_at)
                VALUES (:id, :originalUrl, :displayName, 'feed', true, 'ready', NOW(), NOW())
                """)
            .bind("id", id)
            .bind("originalUrl", "https://" + displayName.toLowerCase() + ".example")
            .bind("displayName", displayName)
            .then()
            .block();
    }

    private void insertPost(long id, long sourceId, String canonicalUrl, String title, OffsetDateTime publishedAt, String rawContent) {
        databaseClient.sql("""
                INSERT INTO posts (id, source_id, canonical_url, title, published_at, raw_content, content_hash, ingest_metadata, created_at, updated_at)
                VALUES (:id, :sourceId, :canonicalUrl, :title, :publishedAt, :rawContent, :contentHash, '{"strategy":"feed"}', NOW(), NOW())
                """)
            .bind("id", id)
            .bind("sourceId", sourceId)
            .bind("canonicalUrl", canonicalUrl)
            .bind("title", title)
            .bind("publishedAt", publishedAt)
            .bind("rawContent", rawContent)
            .bind("contentHash", "hash-" + id)
            .then()
            .block();
    }

    private void insertFeedback(long postId, String state) {
        databaseClient.sql("""
                INSERT INTO feedback (post_id, state, created_at, updated_at)
                VALUES (:postId, :state, NOW(), NOW())
                ON CONFLICT (post_id) DO UPDATE SET state = EXCLUDED.state, updated_at = NOW()
                """)
            .bind("postId", postId)
            .bind("state", state)
            .then()
            .block();
    }

    private void insertReadLater(long postId) {
        databaseClient.sql("INSERT INTO read_later (post_id, created_at) VALUES (:postId, NOW())")
            .bind("postId", postId)
            .then()
            .block();
    }

    private void insertAnalysis(long postId, String summary, Map<String, Object> metadata) throws Exception {
        databaseClient.sql("""
                INSERT INTO post_analysis (post_id, summary_ru, metadata_json, created_at, updated_at)
                VALUES (:postId, :summary, :metadataJson, NOW(), NOW())
                """)
            .bind("postId", postId)
            .bind("summary", summary)
            .bind("metadataJson", objectMapper.writeValueAsString(metadata))
            .then()
            .block();
    }

    private OffsetDateTime utc(String value) {
        return OffsetDateTime.parse(value).withOffsetSameInstant(ZoneOffset.UTC);
    }

    @TestConfiguration
    static class FixedClockConfiguration {

        @Bean
        @Primary
        java.time.Clock fixedClock() {
            return java.time.Clock.fixed(java.time.Instant.parse("2026-04-26T12:00:00Z"), ZoneOffset.UTC);
        }
    }
}
