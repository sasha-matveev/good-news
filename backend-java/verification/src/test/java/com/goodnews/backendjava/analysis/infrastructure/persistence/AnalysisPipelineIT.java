package com.goodnews.backendjava.analysis.infrastructure.persistence;

import static org.assertj.core.api.Assertions.assertThat;

import com.goodnews.backendjava.analysis.model.AnalysisResult;
import com.goodnews.migration.MigrationConfiguration;
import java.time.OffsetDateTime;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webtestclient.autoconfigure.AutoConfigureWebTestClient;
import org.springframework.context.annotation.Import;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import reactor.test.StepVerifier;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@AutoConfigureWebTestClient
@Testcontainers(disabledWithoutDocker = true)
@Import(MigrationConfiguration.class)
class AnalysisPipelineIT {
    private static final String STUB =
            """
            {"summary_ru":"Резюме.","topics":["Java"],"format":"tutorial",
            "technical_depth":"advanced","verdict":"interesting","verdict_reason":"Useful.","relevance_score":9}
            """;

    @Container
    static final PostgreSQLContainer<?> POSTGRESQL = new PostgreSQLContainer<>("postgres:16-alpine")
            .withDatabaseName("good_news")
            .withUsername("good_news")
            .withPassword("good-news-secret");

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("good-news.database.postgres-host", POSTGRESQL::getHost);
        registry.add("good-news.database.postgres-port", POSTGRESQL::getFirstMappedPort);
        registry.add("good-news.database.postgres-database", POSTGRESQL::getDatabaseName);
        registry.add("good-news.database.postgres-user", POSTGRESQL::getUsername);
        registry.add("good-news.database.postgres-password", POSTGRESQL::getPassword);
        registry.add("good-news.app.analysis-stub-response-json", () -> STUB);
        registry.add("good-news.gemini.api-key", () -> "stub-must-win");
    }

    @Autowired
    R2dbcAnalysisRepository repository;

    @Autowired
    DatabaseClient database;

    @Autowired
    WebTestClient client;

    @BeforeEach
    void clean() {
        database.sql("TRUNCATE TABLE post_analysis, feedback, posts, sources RESTART IDENTITY CASCADE")
                .then()
                .block();
        sql("INSERT INTO sources(id,original_url,display_name) VALUES (1,'https://source.test','Source')");
    }

    @Test
    void insertAndUpdatePreserveCreatedTimestampAndMetadata() {
        post(1);
        StepVerifier.create(repository.saveResults(List.of(result(1, 4)))).verifyComplete();
        AnalysisRow inserted = row(1);
        sql("UPDATE post_analysis SET updated_at='2020-01-01T00:00:00Z' WHERE post_id=1");

        StepVerifier.create(repository.saveResults(List.of(result(1, 8)))).verifyComplete();
        AnalysisRow updated = row(1);

        assertThat(updated.createdAt()).isEqualTo(inserted.createdAt());
        assertThat(updated.updatedAt()).isAfter(OffsetDateTime.parse("2020-01-01T00:00:00Z"));
        assertThat(updated.metadata()).contains("\"relevance_score\":8", "\"technical_depth\":\"advanced\"");
    }

    @Test
    void failedChunkRollsBackAllUpserts() {
        post(1);
        StepVerifier.create(repository.saveResults(List.of(result(1, 8), result(999, 8))))
                .expectError()
                .verify();
        assertThat(count("SELECT COUNT(*) AS value FROM post_analysis")).isZero();
    }

    @Test
    void analyzeNowUsesStubAheadOfGeminiPersistsAndReportsCounts() {
        post(1);
        post(2);
        client.post()
                .uri("/api/monitoring/analyze-now")
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .json("{\"analyzed\":2,\"remaining\":0}");
        assertThat(count("SELECT COUNT(*) AS value FROM post_analysis")).isEqualTo(2L);
        assertThat(row(1).metadata()).contains("\"relevance_score\":9");
    }

    private void post(long id) {
        database.sql(
                        """
                INSERT INTO posts(id,source_id,canonical_url,title,raw_content,content_hash,ingest_metadata)
                VALUES (:id,1,:url,:title,'Body',:hash,'{}')
                """)
                .bind("id", id)
                .bind("url", "https://post.test/" + id)
                .bind("title", "Post " + id)
                .bind("hash", "hash-" + id)
                .then()
                .block();
    }

    private AnalysisResult result(long postId, int score) {
        return new AnalysisResult(
                postId, "Резюме.", List.of("Java"), "tutorial", "advanced", "interesting", "Useful.", score);
    }

    private AnalysisRow row(long postId) {
        return database.sql("SELECT created_at, updated_at, metadata_json FROM post_analysis WHERE post_id=:postId")
                .bind("postId", postId)
                .map((row, metadata) -> new AnalysisRow(
                        row.get("created_at", OffsetDateTime.class),
                        row.get("updated_at", OffsetDateTime.class),
                        row.get("metadata_json", String.class)))
                .one()
                .block();
    }

    private long count(String statement) {
        return database.sql(statement)
                .map((row, metadata) -> row.get("value", Long.class))
                .one()
                .block();
    }

    private void sql(String statement) {
        database.sql(statement).then().block();
    }

    private record AnalysisRow(OffsetDateTime createdAt, OffsetDateTime updatedAt, String metadata) {}
}
