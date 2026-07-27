package com.goodnews.backendjava.ingestion.infrastructure.persistence;

import static org.assertj.core.api.Assertions.assertThat;

import com.goodnews.backendjava.ingestion.application.port.SourceReloadWriter;
import com.goodnews.backendjava.ingestion.model.CandidatePost;
import com.goodnews.backendjava.ingestion.model.PublicationDateSource;
import com.goodnews.backendjava.ingestion.model.SourceDefinition;
import com.goodnews.backendjava.ingestion.model.SourceStrategyKind;
import com.goodnews.backendjava.ingestion.model.SourceStrategyOptions;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import reactor.test.StepVerifier;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@Testcontainers(disabledWithoutDocker = true)
class R2dbcSourceReloadWriterIT {
    private static final Instant NOW = Instant.parse("2026-07-13T12:00:00Z");

    @Container
    static final PostgreSQLContainer<?> POSTGRESQL = new PostgreSQLContainer<>("postgres:16-alpine")
            .withDatabaseName("good_news")
            .withUsername("good_news")
            .withPassword("good-news-secret");

    @DynamicPropertySource
    static void databaseProperties(DynamicPropertyRegistry registry) {
        registry.add("good-news.migration.run", () -> true);
        registry.add("good-news.database.postgres-host", POSTGRESQL::getHost);
        registry.add("good-news.database.postgres-port", POSTGRESQL::getFirstMappedPort);
        registry.add("good-news.database.postgres-database", POSTGRESQL::getDatabaseName);
        registry.add("good-news.database.postgres-user", POSTGRESQL::getUsername);
        registry.add("good-news.database.postgres-password", POSTGRESQL::getPassword);
    }

    @Autowired
    R2dbcSourceReloadWriter writer;

    @Autowired
    DatabaseClient database;

    @Test
    void reloadDeletesDigestItemsForReplacedPostsButKeepsTheirDigest() {
        long sourceId = insert(
                """
                INSERT INTO sources (original_url, feed_url, strategy_kind, strategy_config)
                VALUES ('https://source.test', 'https://source.test/feed', 'feed', '{}') RETURNING id
                """,
                Long.class);
        long postId = insert(
                """
                INSERT INTO posts (source_id, canonical_url, title, published_at, raw_content, content_hash, ingest_metadata)
                VALUES (:sourceId, 'https://post.test/old', 'Old', :publishedAt, 'old content', 'old-hash', '{}') RETURNING id
                """,
                Long.class,
                "sourceId",
                sourceId,
                "publishedAt",
                NOW);
        long digestId = insert(
                """
                INSERT INTO digests (digest_type, scheduled_for, status)
                VALUES ('daily', :scheduledFor, 'sent') RETURNING id
                """,
                Long.class,
                "scheduledFor",
                NOW);
        database.sql("INSERT INTO digest_items (digest_id, post_id, rank_position) VALUES (:digestId, :postId, 1)")
                .bind("digestId", digestId)
                .bind("postId", postId)
                .then()
                .block();

        SourceDefinition source = new SourceDefinition(
                sourceId,
                "https://source.test",
                "https://source.test/feed",
                SourceStrategyKind.FEED,
                SourceStrategyOptions.empty(),
                null);
        CandidatePost replacement =
                new CandidatePost("https://post.test/new", "New", NOW, "new content", PublicationDateSource.NONE);

        StepVerifier.create(writer.replaceRecentPosts(source, java.util.List.of(replacement), NOW.minusSeconds(1), NOW))
                .assertNext(result -> assertThat(result).isEqualTo(new SourceReloadWriter.ReloadWriteResult(1, 1)))
                .verifyComplete();

        assertThat(scalar("SELECT COUNT(*) AS value FROM digests WHERE id=" + digestId, Long.class))
                .isEqualTo(1L);
        assertThat(scalar("SELECT COUNT(*) AS value FROM digest_items WHERE digest_id=" + digestId, Long.class))
                .isZero();
        assertThat(scalar("SELECT COUNT(*) AS value FROM posts WHERE source_id=" + sourceId, Long.class))
                .isEqualTo(1L);
    }

    private <T> T insert(String sql, Class<T> type, Object... bindings) {
        DatabaseClient.GenericExecuteSpec query = database.sql(sql);
        for (int index = 0; index < bindings.length; index += 2) {
            query = query.bind((String) bindings[index], bindings[index + 1]);
        }
        return query.map((row, metadata) -> row.get("id", type)).one().block();
    }

    private <T> T scalar(String sql, Class<T> type) {
        return database.sql(sql)
                .map((row, metadata) -> row.get("value", type))
                .one()
                .block();
    }
}
