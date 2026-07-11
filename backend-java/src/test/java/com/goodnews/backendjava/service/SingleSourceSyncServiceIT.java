package com.goodnews.backendjava.service;

import static org.assertj.core.api.Assertions.assertThat;

import com.goodnews.backendjava.ingestion.application.SyncSingleSource;
import com.goodnews.backendjava.ingestion.infrastructure.http.PublicSourceUrlPolicy;
import java.io.IOException;
import java.net.InetAddress;
import java.net.URI;
import java.util.List;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;
import reactor.test.StepVerifier;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@Testcontainers(disabledWithoutDocker = true)
class SingleSourceSyncServiceIT {
    @TestConfiguration
    static class LocalOriginPolicy {
        @Bean
        @Primary
        PublicSourceUrlPolicy sourceUrlPolicy() {
            return new PublicSourceUrlPolicy() {
                @Override
                public Mono<ValidatedUrl> validate(String rawUrl) {
                    return Mono.just(new ValidatedUrl(URI.create(rawUrl), List.of(InetAddress.getLoopbackAddress())));
                }
            };
        }
    }

    @Container
    static final PostgreSQLContainer<?> POSTGRESQL = new PostgreSQLContainer<>("postgres:16-alpine")
            .withDatabaseName("good_news")
            .withUsername("good_news")
            .withPassword("good-news-secret");

    static MockWebServer origin;

    @DynamicPropertySource
    static void databaseProperties(DynamicPropertyRegistry registry) {
        registry.add("good-news.database.postgres-host", POSTGRESQL::getHost);
        registry.add("good-news.database.postgres-port", POSTGRESQL::getFirstMappedPort);
        registry.add("good-news.database.postgres-database", POSTGRESQL::getDatabaseName);
        registry.add("good-news.database.postgres-user", POSTGRESQL::getUsername);
        registry.add("good-news.database.postgres-password", POSTGRESQL::getPassword);
    }

    @BeforeAll
    static void startOrigin() throws IOException {
        origin = new MockWebServer();
        origin.start();
    }

    @AfterAll
    static void stopOrigin() throws IOException {
        origin.shutdown();
    }

    @Autowired
    SyncSingleSource service;

    @Autowired
    DatabaseClient databaseClient;

    @Test
    void syncPersistsPostsDeduplicatesAndMarksSourceReady() {
        String feedUrl = origin.url("/feed").toString();
        long id = insertSource(feedUrl, "ready", 2);
        String feed =
                """
            <rss><channel>
              <item><title>First</title><link>https://articles.test/first</link><description>Same body</description></item>
              <item><title>URL duplicate</title><link>https://articles.test/first</link><description>Different</description></item>
              <item><title>Hash duplicate</title><link>https://articles.test/second</link><description>Same body</description></item>
            </channel></rss>
            """;
        origin.enqueue(new MockResponse().setResponseCode(200).setBody(feed));

        StepVerifier.create(service.sync(id))
                .assertNext(outcome -> assertThat(outcome.processedSourceIds()).containsExactly(id))
                .verifyComplete();

        assertThat(scalar("SELECT COUNT(*) AS value FROM posts WHERE source_id=" + id, Long.class))
                .isEqualTo(1L);
        assertThat(scalar("SELECT status AS value FROM sources WHERE id=" + id, String.class))
                .isEqualTo("ready");
        assertThat(scalar("SELECT consecutive_failures AS value FROM sources WHERE id=" + id, Integer.class))
                .isZero();
        assertThat(scalar("SELECT ingest_metadata AS value FROM posts WHERE source_id=" + id, String.class))
                .contains("\"source_strategy\":\"feed\"")
                .contains("\"date_source\":\"none\"");

        origin.enqueue(new MockResponse().setResponseCode(200).setBody(feed));
        service.sync(id).block();
        assertThat(scalar("SELECT COUNT(*) AS value FROM posts WHERE source_id=" + id, Long.class))
                .isEqualTo(1L);
    }

    @Test
    void failedFetchMarksSourceFailingAndReturnsNoProcessedId() {
        String feedUrl = origin.url("/missing").toString();
        long id = insertSource(feedUrl, "ready", 0);
        origin.enqueue(new MockResponse().setResponseCode(404));

        StepVerifier.create(service.sync(id))
                .assertNext(outcome -> assertThat(outcome.processedSourceIds()).isEmpty())
                .verifyComplete();

        assertThat(scalar("SELECT status AS value FROM sources WHERE id=" + id, String.class))
                .isEqualTo("failing");
        assertThat(scalar("SELECT consecutive_failures AS value FROM sources WHERE id=" + id, Integer.class))
                .isEqualTo(1);
        assertThat(scalar("SELECT last_failure_at IS NOT NULL AS value FROM sources WHERE id=" + id, Boolean.class))
                .isTrue();
    }

    @Test
    void concurrentSyncsAtomicallyDeduplicateGlobalPostIdentityAndContent() {
        String feedUrl = origin.url("/concurrent-feed").toString();
        long id = insertSource(feedUrl, "ready", 0);
        String feed =
                """
                <rss><channel><item><title>Concurrent</title>
                <link>https://articles.test/concurrent</link><description>Identical content</description>
                </item></channel></rss>
                """;
        origin.enqueue(new MockResponse().setResponseCode(200).setBody(feed));
        origin.enqueue(new MockResponse().setResponseCode(200).setBody(feed));

        StepVerifier.create(Mono.zip(
                        service.sync(id).subscribeOn(Schedulers.parallel()),
                        service.sync(id).subscribeOn(Schedulers.parallel())))
                .assertNext(outcomes -> {
                    assertThat(outcomes.getT1().processedSourceIds()).containsExactly(id);
                    assertThat(outcomes.getT2().processedSourceIds()).containsExactly(id);
                })
                .verifyComplete();

        assertThat(scalar(
                        "SELECT COUNT(*) AS value FROM posts WHERE canonical_url="
                                + "'https://articles.test/concurrent'",
                        Long.class))
                .isEqualTo(1L);
        assertThat(scalar("SELECT COUNT(DISTINCT content_hash) AS value FROM posts WHERE source_id=" + id, Long.class))
                .isEqualTo(1L);
    }

    private long insertSource(String feedUrl, String status, int failures) {
        return databaseClient
                .sql(
                        """
            INSERT INTO sources (original_url, feed_url, strategy_kind, strategy_config, status, consecutive_failures)
            VALUES (:url, :url, 'feed', '{}', :status, :failures) RETURNING id
            """)
                .bind("url", feedUrl)
                .bind("status", status)
                .bind("failures", failures)
                .map((row, metadata) -> row.get("id", Long.class))
                .one()
                .block();
    }

    private <T> T scalar(String sql, Class<T> type) {
        return databaseClient
                .sql(sql)
                .map((row, metadata) -> row.get("value", type))
                .one()
                .block();
    }
}
