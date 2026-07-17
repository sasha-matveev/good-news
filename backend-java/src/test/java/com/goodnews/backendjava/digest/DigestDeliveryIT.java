package com.goodnews.backendjava.digest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.reset;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

import com.goodnews.backendjava.service.JakartaMailSmtpEmailAdapter;
import com.goodnews.backendjava.service.SmtpEmailAdapter;
import io.micrometer.core.instrument.MeterRegistry;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.SpyBean;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import reactor.core.publisher.Mono;

@SpringBootTest
@Testcontainers(disabledWithoutDocker = true)
class DigestDeliveryIT {
    private static final Instant NOW = Instant.parse("2026-07-17T12:00:00Z");

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
        registry.add("good-news.email.public-content-api-origin", () -> "https://api.good-news.example/");
        registry.add("good-news.email.public-frontend-origin", () -> "https://good-news.example/");
    }

    @Autowired
    DigestDeliveryService delivery;

    @Autowired
    DatabaseClient database;

    @Autowired
    MeterRegistry meters;

    @SpyBean
    JakartaMailSmtpEmailAdapter smtp;

    @SpyBean
    DigestRepository digests;

    @SpyBean
    DigestGenerationService generator;

    @BeforeEach
    void clean() {
        reset(smtp, digests, generator);
        database.sql(
                        "TRUNCATE TABLE digest_items, digests, read_later, post_analysis, feedback, technical_events, posts, sources, secret_settings, settings RESTART IDENTITY CASCADE")
                .then()
                .block();
        sql("INSERT INTO sources(id,original_url,display_name) VALUES (1,'https://source.test','Source')");
    }

    @Test
    void dailyGenerationRanksPersistsRendersAndSendsOnBoundedElastic() {
        double sentBefore = deliveryRuns("daily", "sent");
        MockSmtpServer server = new MockSmtpServer();
        smtpSettings(server.port());
        for (int id = 1; id <= 7; id++) {
            post(id, NOW.minusSeconds(3600), id);
        }
        post(8, NOW.minusSeconds(2 * 24 * 3600), 10);
        post(9, NOW.plusSeconds(3600), 10);
        List<String> threadNames = new CopyOnWriteArrayList<>();
        doAnswer(invocation -> {
                    threadNames.add(Thread.currentThread().getName());
                    return invocation.callRealMethod();
                })
                .when(smtp)
                .send(any(), any());

        DeliveryRunResult result = delivery.deliverDaily(NOW).block();

        assertThat(result).isEqualTo(new DeliveryRunResult(1, "sent", true, 5));
        assertThat(threadNames).singleElement().satisfies(name -> assertThat(name)
                .contains("boundedElastic"));
        ArgumentCaptor<SmtpEmailAdapter.TestEmailMessage> message =
                ArgumentCaptor.forClass(SmtpEmailAdapter.TestEmailMessage.class);
        verify(smtp).send(message.capture(), any());
        assertThat(message.getValue().subject()).isEqualTo("Good News digest for 2026-07-17");
        assertThat(message.getValue().htmlBody())
                .contains("digest_id=1", "...and 2 more posts", "https://api.good-news.example/api/feedback")
                .doesNotContain("Post 8", "Post 9");
        assertThat(server.message()).contains("Subject: Good News digest for 2026-07-17", "Post 7");
        server.close();

        DigestRow digest = digest(1);
        assertThat(digest.status()).isEqualTo("sent");
        assertThat(digest.recipient()).isEqualTo("reader@example.com");
        assertThat(digest.sentAt().toInstant()).isEqualTo(NOW);
        assertThat(digest.metadata()).isEqualTo("{\"frontend_base_url\":\"https://good-news.example\"}");
        assertThat(itemPostIds(1)).containsExactly(7L, 6L, 5L, 4L, 3L);
        assertThat(setting("last_daily_digest_sent_at")).isEqualTo(NOW.toString());
        assertThat(deliveryRuns("daily", "sent")).isEqualTo(sentBefore + 1);
    }

    @Test
    void weeklyIncludesOlderPostsAndUsesWeeklyHistoryKey() {
        double sentBefore = deliveryRuns("weekly", "sent");
        MockSmtpServer server = new MockSmtpServer();
        smtpSettings(server.port());
        post(1, NOW.minusSeconds(3 * 24 * 3600), 8);

        DeliveryRunResult result = delivery.deliverWeekly(NOW).block();

        assertThat(result.status()).isEqualTo("sent");
        assertThat(digest(1).type()).isEqualTo("weekly");
        assertThat(itemPostIds(1)).containsExactly(1L);
        assertThat(setting("last_weekly_digest_sent_at")).isEqualTo(NOW.toString());
        assertThat(server.message()).contains("Subject: Good News weekly digest for 2026-07-17", "Post 1");
        server.close();
        assertThat(deliveryRuns("weekly", "sent")).isEqualTo(sentBefore + 1);
    }

    @Test
    void missingRecipientSkipsDeliveryButAdvancesHistory() {
        double skippedBefore = deliveryRuns("daily", "skipped");
        setting("sender_identity", "sender@example.com");
        post(1, NOW.minusSeconds(3600), 5);

        DeliveryRunResult result = delivery.deliverDaily(NOW).block();

        assertThat(result.status()).isEqualTo("skipped");
        assertThat(result.delivered()).isFalse();
        assertThat(digest(1).status()).isEqualTo("skipped");
        assertThat(setting("last_daily_digest_sent_at")).isEqualTo(NOW.toString());
        verifyNoInteractions(smtp);
        assertThat(deliveryRuns("daily", "skipped")).isEqualTo(skippedBefore + 1);
    }

    @Test
    void smtpFailureMarksPersistedDigestIndeterminateAndDoesNotAdvanceHistory() {
        double indeterminateBefore = deliveryRuns("daily", "indeterminate");
        smtpSettings(2525);
        post(1, NOW.minusSeconds(3600), 5);
        doThrow(new IllegalStateException("SMTP unavailable")).when(smtp).send(any(), any());

        assertThatThrownBy(() -> delivery.deliverDaily(NOW).block())
                .hasMessage("SMTP delivery outcome is indeterminate")
                .hasRootCauseMessage("SMTP unavailable");

        assertThat(digest(1).status()).isEqualTo("indeterminate");
        assertThat(setting("last_daily_digest_sent_at")).isNull();
        assertThat(deliveryRuns("daily", "indeterminate")).isEqualTo(indeterminateBefore + 1);
    }

    @Test
    void indeterminateMetricSurvivesFailureToPersistSmtpOutcome() {
        double indeterminateBefore = deliveryRuns("daily", "indeterminate");
        smtpSettings(2525);
        post(1, NOW.minusSeconds(3600), 5);
        doThrow(new IllegalStateException("SMTP unavailable")).when(smtp).send(any(), any());
        doReturn(Mono.error(new IllegalStateException("DB unavailable")))
                .when(digests)
                .markIndeterminate(anyLong());

        assertThatThrownBy(() -> delivery.deliverDaily(NOW).block())
                .hasMessage("Delivery outcome is indeterminate and could not be persisted")
                .hasRootCauseMessage("SMTP unavailable");

        assertThat(digest(1).status()).isEqualTo("generated");
        assertThat(deliveryRuns("daily", "indeterminate")).isEqualTo(indeterminateBefore + 1);
    }

    @Test
    void existingScheduledRunPreventsDuplicateSmtpDelivery() {
        double blockedBefore = deliveryRuns("daily", "duplicate_blocked");
        MockSmtpServer server = new MockSmtpServer();
        smtpSettings(server.port());
        post(1, NOW.minusSeconds(3600), 5);

        delivery.deliverDaily(NOW).block();
        assertThat(server.message()).contains("Post 1");
        server.close();

        assertThatThrownBy(() -> delivery.deliverDaily(NOW).block())
                .hasMessageContaining("Digest run already exists")
                .hasMessageContaining("status sent");
        verify(smtp, times(1)).send(any(), any());
        assertThat(count("SELECT COUNT(*) AS value FROM digests")).isEqualTo(1L);
        assertThat(deliveryRuns("daily", "duplicate_blocked")).isEqualTo(blockedBefore + 1);
    }

    @Test
    void indeterminateScheduledRunRequiresOperatorResolutionInsteadOfResending() {
        double indeterminateBefore = deliveryRuns("daily", "indeterminate");
        sql(
                "INSERT INTO digests(digest_type,scheduled_for,status) VALUES ('daily','2026-07-17T12:00:00Z','indeterminate')");

        assertThatThrownBy(() -> delivery.deliverDaily(NOW).block())
                .hasMessageContaining("Digest run already exists")
                .hasMessageContaining("status indeterminate");

        verifyNoInteractions(smtp);
        assertThat(count("SELECT COUNT(*) AS value FROM digests")).isEqualTo(1L);
        assertThat(deliveryRuns("daily", "indeterminate")).isEqualTo(indeterminateBefore + 1);
    }

    @Test
    void legacySentRunIsNotHiddenByNewerFailedDuplicate() {
        double blockedBefore = deliveryRuns("daily", "duplicate_blocked");
        sql(
                "INSERT INTO digests(digest_type,scheduled_for,status) VALUES ('daily','2026-07-17T12:00:00Z','sent'),('daily','2026-07-17T12:00:00Z','failed')");

        assertThatThrownBy(() -> delivery.deliverDaily(NOW).block()).hasMessageContaining("status sent");

        verifyNoInteractions(smtp);
        assertThat(count("SELECT COUNT(*) AS value FROM digests")).isEqualTo(2L);
        assertThat(deliveryRuns("daily", "duplicate_blocked")).isEqualTo(blockedBefore + 1);
    }

    @Test
    void postSmtpPersistenceFailureBecomesIndeterminateAndCannotResend() {
        double indeterminateBefore = deliveryRuns("daily", "indeterminate");
        MockSmtpServer server = new MockSmtpServer();
        smtpSettings(server.port());
        post(1, NOW.minusSeconds(3600), 5);
        doReturn(Mono.error(new IllegalStateException("DB unavailable")))
                .when(digests)
                .markSent(anyLong(), anyString(), any(Instant.class));

        assertThatThrownBy(() -> delivery.deliverDaily(NOW).block())
                .hasMessage("SMTP accepted the message, but delivery state could not be persisted");
        assertThat(server.message()).contains("Post 1");
        server.close();
        assertThat(digest(1).status()).isEqualTo("indeterminate");

        reset(digests);
        assertThatThrownBy(() -> delivery.deliverDaily(NOW).block()).hasMessageContaining("status indeterminate");
        verify(smtp, times(1)).send(any(), any());
        assertThat(deliveryRuns("daily", "indeterminate")).isEqualTo(indeterminateBefore + 2);
    }

    @Test
    void generationFailureIsRecordedByDeliveryWorkflow() {
        double failedBefore = deliveryRuns("daily", "failed");
        doReturn(Mono.error(new IllegalStateException("generation failed")))
                .when(generator)
                .generateDaily(NOW);

        assertThatThrownBy(() -> delivery.deliverDaily(NOW).block()).hasMessage("generation failed");

        verifyNoInteractions(smtp);
        assertThat(count("SELECT COUNT(*) AS value FROM digests")).isZero();
        assertThat(deliveryRuns("daily", "failed")).isEqualTo(failedBefore + 1);
    }

    @Test
    void concurrentRunsClaimOneDatabaseSlotAndSendOnlyOnce() {
        double blockedBefore = deliveryRuns("daily", "duplicate_blocked");
        MockSmtpServer server = new MockSmtpServer();
        smtpSettings(server.port());
        post(1, NOW.minusSeconds(3600), 5);

        List<String> outcomes = Mono.zip(
                        delivery.deliverDaily(NOW)
                                .map(DeliveryRunResult::status)
                                .onErrorReturn("blocked"),
                        delivery.deliverDaily(NOW)
                                .map(DeliveryRunResult::status)
                                .onErrorReturn("blocked"))
                .map(tuple -> List.of(tuple.getT1(), tuple.getT2()))
                .block();

        assertThat(outcomes).containsExactlyInAnyOrder("sent", "blocked");
        assertThat(server.message()).contains("Post 1");
        server.close();
        verify(smtp, times(1)).send(any(), any());
        assertThat(count("SELECT COUNT(*) AS value FROM digests")).isEqualTo(1L);
        assertThat(deliveryRuns("daily", "duplicate_blocked")).isEqualTo(blockedBefore + 1);
    }

    private void smtpSettings(int port) {
        setting("recipient_email", "reader@example.com");
        setting("sender_identity", "sender@example.com");
        setting("smtp_host", "127.0.0.1");
        setting("smtp_port", Integer.toString(port));
        setting("smtp_security_mode", "none");
    }

    private void post(int id, Instant publishedAt, int relevanceScore) {
        database.sql(
                        """
                INSERT INTO posts(id,source_id,canonical_url,title,published_at,raw_content,content_hash,ingest_metadata)
                VALUES (:id,1,:url,:title,:publishedAt,'Body',:hash,'{}')
                """)
                .bind("id", id)
                .bind("url", "https://post.test/" + id)
                .bind("title", "Post " + id)
                .bind("publishedAt", OffsetDateTime.parse(publishedAt.toString()))
                .bind("hash", "hash-" + id)
                .then()
                .block();
        database.sql(
                        """
                INSERT INTO post_analysis(post_id,summary_ru,metadata_json)
                VALUES (:postId,:summary,:metadata)
                """)
                .bind("postId", id)
                .bind("summary", "Summary " + id)
                .bind(
                        "metadata",
                        "{\"verdict\":\"interesting\",\"verdict_reason\":\"Reason\",\"relevance_score\":"
                                + relevanceScore + "}")
                .then()
                .block();
    }

    private DigestRow digest(long id) {
        return database.sql("SELECT digest_type,status,recipient_email,sent_at,metadata_json FROM digests WHERE id=:id")
                .bind("id", id)
                .map((row, metadata) -> new DigestRow(
                        row.get("digest_type", String.class),
                        row.get("status", String.class),
                        row.get("recipient_email", String.class),
                        row.get("sent_at", OffsetDateTime.class),
                        row.get("metadata_json", String.class)))
                .one()
                .block();
    }

    private List<Long> itemPostIds(long digestId) {
        return database.sql("SELECT post_id FROM digest_items WHERE digest_id=:digestId ORDER BY rank_position")
                .bind("digestId", digestId)
                .map((row, metadata) -> ((Number) row.get("post_id")).longValue())
                .all()
                .collectList()
                .block();
    }

    private void setting(String key, String value) {
        database.sql("INSERT INTO settings(key,value) VALUES (:key,:value)")
                .bind("key", key)
                .bind("value", value)
                .then()
                .block();
    }

    private String setting(String key) {
        return database.sql("SELECT value FROM settings WHERE key=:key")
                .bind("key", key)
                .map((row, metadata) -> row.get("value", String.class))
                .one()
                .block();
    }

    private void sql(String statement) {
        database.sql(statement).then().block();
    }

    private long count(String statement) {
        return database.sql(statement)
                .map((row, metadata) -> row.get("value", Long.class))
                .one()
                .block();
    }

    private double deliveryRuns(String type, String status) {
        var counter = meters.find("good.news.delivery.runs")
                .tags("digest_type", type, "status", status)
                .counter();
        return counter == null ? 0 : counter.count();
    }

    private record DigestRow(String type, String status, String recipient, OffsetDateTime sentAt, String metadata) {}

    private static final class MockSmtpServer implements AutoCloseable {
        private final ServerSocket serverSocket;
        private final CompletableFuture<String> message = new CompletableFuture<>();
        private final Thread thread;

        private MockSmtpServer() {
            try {
                serverSocket = new ServerSocket(0);
            } catch (IOException exception) {
                throw new IllegalStateException("Could not start mock SMTP server", exception);
            }
            thread = Thread.ofVirtual().start(this::serve);
        }

        private int port() {
            return serverSocket.getLocalPort();
        }

        private String message() {
            try {
                return message.get(5, TimeUnit.SECONDS);
            } catch (Exception exception) {
                throw new IllegalStateException("Mock SMTP server did not receive a message", exception);
            }
        }

        private void serve() {
            try (Socket socket = serverSocket.accept();
                    BufferedReader reader = new BufferedReader(
                            new InputStreamReader(socket.getInputStream(), StandardCharsets.US_ASCII));
                    BufferedWriter writer = new BufferedWriter(
                            new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.US_ASCII))) {
                reply(writer, "220 mock-smtp ready");
                StringBuilder content = new StringBuilder();
                boolean readingData = false;
                String line;
                while ((line = reader.readLine()) != null) {
                    if (readingData) {
                        if (".".equals(line)) {
                            message.complete(content.toString());
                            readingData = false;
                            reply(writer, "250 queued");
                        } else {
                            content.append(line).append('\n');
                        }
                    } else if (line.regionMatches(true, 0, "EHLO", 0, 4) || line.regionMatches(true, 0, "HELO", 0, 4)) {
                        reply(writer, "250 mock-smtp");
                    } else if (line.equalsIgnoreCase("DATA")) {
                        readingData = true;
                        reply(writer, "354 end with dot");
                    } else if (line.equalsIgnoreCase("QUIT")) {
                        reply(writer, "221 bye");
                        return;
                    } else {
                        reply(writer, "250 ok");
                    }
                }
            } catch (Exception exception) {
                message.completeExceptionally(exception);
            }
        }

        private void reply(BufferedWriter writer, String value) throws IOException {
            writer.write(value);
            writer.write("\r\n");
            writer.flush();
        }

        @Override
        public void close() {
            try {
                serverSocket.close();
                thread.join(TimeUnit.SECONDS.toMillis(5));
            } catch (Exception exception) {
                throw new IllegalStateException("Could not close mock SMTP server", exception);
            }
        }
    }
}
