package com.goodnews.backendjava.api;

import static org.assertj.core.api.Assertions.assertThat;

import com.goodnews.backendjava.service.SmtpEmailAdapter;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.webtestclient.autoconfigure.AutoConfigureWebTestClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import tools.jackson.databind.ObjectMapper;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@AutoConfigureWebTestClient
@Testcontainers(disabledWithoutDocker = true)
class PreferencesSettingsApiTest {

    private static final String DEFAULT_SUMMARY_INSTRUCTIONS =
            """
        a detailed summary in Russian (Кириллица), 4-6 sentences (roughly 60-120 words). Cover what the article is about, its key points, arguments or findings, and the concrete takeaway — enough that the reader understands the substance without opening the article. Do not just rephrase the title; add the specifics from the body. Use only Russian words — no Latin, no code, no transliteration. If you cannot write proper Russian, use "".
        """
                    .strip();
    private static final String DEFAULT_VERDICT_REASON_INSTRUCTIONS =
            """
        1 sentence in ENGLISH explaining why THIS reader (given the reader preference profile above, when present) would or would not want to read this. MUST be in English. No Russian.
        """
                    .strip();

    @Container
    static final PostgreSQLContainer<?> POSTGRESQL = new PostgreSQLContainer<>("postgres:16-alpine")
            .withDatabaseName("good_news")
            .withUsername("good_news")
            .withPassword("good-news-secret");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("good-news.migration.run", () -> true);
        registry.add("good-news.database.postgres-host", POSTGRESQL::getHost);
        registry.add("good-news.database.postgres-port", POSTGRESQL::getFirstMappedPort);
        registry.add("good-news.database.postgres-database", POSTGRESQL::getDatabaseName);
        registry.add("good-news.database.postgres-user", POSTGRESQL::getUsername);
        registry.add("good-news.database.postgres-password", POSTGRESQL::getPassword);
        registry.add("good-news.email.app-master-key", () -> "test-master-key");
        registry.add("good-news.email.public-frontend-origin", () -> "https://good-news.example");
    }

    @Autowired
    private WebTestClient webTestClient;

    @Autowired
    private DatabaseClient databaseClient;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private RecordingSmtpEmailAdapter recordingSmtpEmailAdapter;

    @BeforeEach
    void cleanDatabase() {
        recordingSmtpEmailAdapter.reset();
        databaseClient
                .sql(
                        """
                TRUNCATE TABLE preference_profile, secret_settings, settings, read_later, post_analysis, feedback, posts, sources
                RESTART IDENTITY CASCADE
                """)
                .then()
                .block();
    }

    @Test
    void getPreferencesReturnsPersistedAggregateExplanations() throws Exception {
        insertSource(1, "Alpha");
        insertPost(
                1,
                1,
                "https://alpha.example/posts/1",
                "Distributed tracing in practice",
                utc("2026-04-20T09:00:00Z"),
                "Deep incident review.");
        insertFeedback(1, "interesting");
        insertPost(
                2,
                1,
                "https://alpha.example/posts/2",
                "Opinionated frontend note",
                utc("2026-04-21T09:00:00Z"),
                "Short take.");
        insertFeedback(2, "not_interesting");
        insertAnalysis(
                1,
                "Русское summary.",
                Map.of(
                        "topics", new String[] {"observability", "distributed-systems"},
                        "format", "postmortem",
                        "technical_depth", "deep",
                        "verdict", "interesting",
                        "verdict_reason", "Dense practical engineering notes."));
        insertAnalysis(
                2,
                "Short summary.",
                Map.of(
                        "topics", new String[] {"frontend"},
                        "format", "opinion",
                        "technical_depth", "shallow",
                        "verdict", "skip",
                        "verdict_reason", "Not practical enough."));

        webTestClient
                .get()
                .uri("/api/preferences")
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .json(
                        """
                {
                  "summary": "From 2 feedback signals, the profile is learning toward distributed systems postmortems from Alpha and away from opinion pieces.",
                  "positive_signals": [
                    "1 positive signal for source Alpha",
                    "1 positive signal for topic distributed systems",
                    "1 positive signal for format postmortem",
                    "1 positive signal for deep technical material"
                  ],
                  "negative_signals": [
                    "1 not-interesting signal against topic frontend",
                    "1 not-interesting signal against format opinion"
                  ],
                  "learning_proof": [
                    "2 feedback decisions recorded: 1 interesting, 0 want to read, 1 not interesting.",
                    "Strongest positive pull: source Alpha and topic distributed systems.",
                    "Strongest negative pull: topic frontend and format opinion."
                  ],
                  "feedback_totals": {
                    "interesting": 1,
                    "not_interesting": 1,
                    "total": 2,
                    "want_to_read": 0
                  }
                }
                """);

        assertThat(queryForString("SELECT summary FROM preference_profile WHERE id = 1"))
                .isEqualTo(
                        "From 2 feedback signals, the profile is learning toward distributed systems postmortems from Alpha and away from opinion pieces.");
    }

    @Test
    void recomputePreferencesCountsFeedbackWithoutAnalysisAndPersists() {
        insertSource(1, "Alpha");
        insertPost(
                1,
                1,
                "https://alpha.example/posts/1",
                "Post without analysis",
                utc("2026-04-20T09:00:00Z"),
                "Content here.");
        insertFeedback(1, "interesting");

        webTestClient
                .post()
                .uri("/api/preferences/recompute")
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .jsonPath("$.feedback_totals.interesting")
                .isEqualTo(1)
                .jsonPath("$.feedback_totals.total")
                .isEqualTo(1);

        assertThat(queryForString("SELECT summary FROM preference_profile WHERE id = 1"))
                .contains("Alpha");
    }

    @Test
    void settingsApiReturnsDefaultsPersistsWriteOnlyPasswordAndResetsBlankPrompts() {
        webTestClient
                .get()
                .uri("/api/settings")
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .jsonPath("$.daily_digest_time")
                .isEqualTo("12:00")
                .jsonPath("$.weekly_digest_day_of_week")
                .isEqualTo("sat")
                .jsonPath("$.weekly_digest_time")
                .isEqualTo("23:30")
                .jsonPath("$.observability_dashboard_url")
                .isEqualTo("http://127.0.0.1:3000/d/good-news-overview/good-news-observability-overview")
                .jsonPath("$.smtp_port")
                .isEqualTo(587)
                .jsonPath("$.smtp_security_mode")
                .isEqualTo("starttls")
                .jsonPath("$.smtp_password_configured")
                .isEqualTo(false)
                .jsonPath("$.analysis_summary_prompt")
                .isEqualTo(DEFAULT_SUMMARY_INSTRUCTIONS)
                .jsonPath("$.analysis_verdict_reason_prompt")
                .isEqualTo(DEFAULT_VERDICT_REASON_INSTRUCTIONS);

        byte[] updateResponse = webTestClient
                .put()
                .uri("/api/settings")
                .bodyValue(
                        settingsPayload().with("smtp_password", "plain-secret").build())
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .jsonPath("$.daily_digest_time")
                .isEqualTo("08:45")
                .jsonPath("$.weekly_digest_day_of_week")
                .isEqualTo("fri")
                .jsonPath("$.weekly_digest_time")
                .isEqualTo("16:30")
                .jsonPath("$.smtp_password_configured")
                .isEqualTo(true)
                .jsonPath("$.analysis_summary_prompt")
                .isEqualTo(DEFAULT_SUMMARY_INSTRUCTIONS)
                .jsonPath("$.analysis_verdict_reason_prompt")
                .isEqualTo(DEFAULT_VERDICT_REASON_INSTRUCTIONS)
                .returnResult()
                .getResponseBody();

        assertThat(new String(updateResponse)).doesNotContain("plain-secret");

        webTestClient
                .put()
                .uri("/api/settings")
                .bodyValue(settingsPayload()
                        .with("analysis_summary_prompt", "   ")
                        .with("analysis_verdict_reason_prompt", "")
                        .build())
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .jsonPath("$.analysis_summary_prompt")
                .isEqualTo(DEFAULT_SUMMARY_INSTRUCTIONS)
                .jsonPath("$.analysis_verdict_reason_prompt")
                .isEqualTo(DEFAULT_VERDICT_REASON_INSTRUCTIONS)
                .jsonPath("$.smtp_password_configured")
                .isEqualTo(true);

        assertThat(queryForString("SELECT value FROM settings WHERE key = 'daily_digest_time'"))
                .isEqualTo("08:45");
        assertThat(queryForString("SELECT encrypted_value FROM secret_settings WHERE key = 'smtp_password'"))
                .isNotEqualTo("plain-secret")
                .isNotBlank();
    }

    @Test
    void settingsApiDefaultsOmittedDigestBooleansWithoutChangingPromptBehavior() {
        webTestClient
                .put()
                .uri("/api/settings")
                .bodyValue(new PayloadBuilder()
                        .with("daily_digest_time", "08:45")
                        .with("weekly_digest_day_of_week", "fri")
                        .with("weekly_digest_time", "16:30")
                        .with("recipient_email", "reader@example.com")
                        .with("sender_identity", "Good News Digest <digest@example.com>")
                        .with("smtp_host", "smtp.example.com")
                        .with("smtp_port", 465)
                        .with("smtp_username", "digest-user")
                        .with("smtp_security_mode", "ssl")
                        .with("analysis_summary_prompt", "")
                        .with("analysis_verdict_reason_prompt", "")
                        .build())
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .jsonPath("$.daily_digest_enabled")
                .isEqualTo(true)
                .jsonPath("$.daily_digest_catch_up_enabled")
                .isEqualTo(true)
                .jsonPath("$.weekly_digest_enabled")
                .isEqualTo(false)
                .jsonPath("$.weekly_digest_catch_up_enabled")
                .isEqualTo(true)
                .jsonPath("$.analysis_summary_prompt")
                .isEqualTo(DEFAULT_SUMMARY_INSTRUCTIONS)
                .jsonPath("$.analysis_verdict_reason_prompt")
                .isEqualTo(DEFAULT_VERDICT_REASON_INSTRUCTIONS);

        assertThat(queryForString("SELECT value FROM settings WHERE key = 'daily_digest_enabled'"))
                .isEqualTo("true");
        assertThat(queryForString("SELECT value FROM settings WHERE key = 'daily_digest_catch_up_enabled'"))
                .isEqualTo("true");
        assertThat(queryForString("SELECT value FROM settings WHERE key = 'weekly_digest_enabled'"))
                .isEqualTo("false");
        assertThat(queryForString("SELECT value FROM settings WHERE key = 'weekly_digest_catch_up_enabled'"))
                .isEqualTo("true");
        assertThat(queryForString(
                        "SELECT COALESCE(value, '__NULL__') FROM settings WHERE key = 'analysis_summary_prompt'"))
                .isEqualTo("__NULL__");
        assertThat(
                        queryForString(
                                "SELECT COALESCE(value, '__NULL__') FROM settings WHERE key = 'analysis_verdict_reason_prompt'"))
                .isEqualTo("__NULL__");
    }

    @Test
    void settingsApiRejectsInvalidUpdates() {
        webTestClient
                .put()
                .uri("/api/settings")
                .bodyValue(new PayloadBuilder()
                        .with("daily_digest_time", "25:99")
                        .with("weekly_digest_day_of_week", "funday")
                        .with("weekly_digest_time", "24:15")
                        .with("smtp_port", 587)
                        .with("smtp_security_mode", "starttls")
                        .with("daily_digest_enabled", true)
                        .with("daily_digest_catch_up_enabled", true)
                        .with("weekly_digest_enabled", true)
                        .with("weekly_digest_catch_up_enabled", true)
                        .with("analysis_summary_prompt", "")
                        .with("analysis_verdict_reason_prompt", "")
                        .build())
                .exchange()
                .expectStatus()
                .isEqualTo(422)
                .expectBody()
                .jsonPath("$.detail[?(@.loc[1]=='daily_digest_time')]")
                .exists()
                .jsonPath("$.detail[?(@.loc[1]=='weekly_digest_day_of_week')]")
                .exists()
                .jsonPath("$.detail[?(@.loc[1]=='weekly_digest_time')]")
                .exists();
    }

    @Test
    void settingsTestEmailUsesAdapterAndRunsOffEventLoop() {
        webTestClient
                .put()
                .uri("/api/settings")
                .bodyValue(settingsPayload()
                        .with("smtp_password", "plain-secret")
                        .with("analysis_summary_prompt", "Custom summary")
                        .with("analysis_verdict_reason_prompt", "Custom verdict")
                        .build())
                .exchange()
                .expectStatus()
                .isOk();

        webTestClient
                .post()
                .uri("/api/settings/test-email")
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .json("{\"status\":\"sent\"}");

        assertThat(recordingSmtpEmailAdapter.message()).isNotNull();
        assertThat(recordingSmtpEmailAdapter.message().sender()).isEqualTo("Good News Digest <digest@example.com>");
        assertThat(recordingSmtpEmailAdapter.message().recipient()).isEqualTo("reader@example.com");
        assertThat(recordingSmtpEmailAdapter.connectionSettings().host()).isEqualTo("smtp.example.com");
        assertThat(recordingSmtpEmailAdapter.connectionSettings().port()).isEqualTo(465);
        assertThat(recordingSmtpEmailAdapter.connectionSettings().username()).isEqualTo("digest-user");
        assertThat(recordingSmtpEmailAdapter.connectionSettings().password()).isEqualTo("plain-secret");
        assertThat(recordingSmtpEmailAdapter.connectionSettings().securityMode())
                .isEqualTo("ssl");
        assertThat(recordingSmtpEmailAdapter.nonBlockingThread()).isFalse();
        assertThat(recordingSmtpEmailAdapter.threadName()).contains("boundedElastic");
    }

    private void insertSource(long id, String displayName) {
        databaseClient
                .sql(
                        """
                INSERT INTO sources (id, original_url, display_name, strategy_kind, active, status, created_at, updated_at)
                VALUES (:id, :originalUrl, :displayName, 'feed', true, 'ready', NOW(), NOW())
                """)
                .bind("id", id)
                .bind("originalUrl", "https://" + displayName.toLowerCase() + ".example")
                .bind("displayName", displayName)
                .then()
                .block();
    }

    private void insertPost(
            long id, long sourceId, String canonicalUrl, String title, OffsetDateTime publishedAt, String rawContent) {
        databaseClient
                .sql(
                        """
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
        databaseClient
                .sql(
                        """
                INSERT INTO feedback (post_id, state, created_at, updated_at)
                VALUES (:postId, :state, NOW(), NOW())
                ON CONFLICT (post_id) DO UPDATE SET state = EXCLUDED.state, updated_at = NOW()
                """)
                .bind("postId", postId)
                .bind("state", state)
                .then()
                .block();
    }

    private void insertAnalysis(long postId, String summary, Map<String, Object> metadata) throws Exception {
        databaseClient
                .sql(
                        """
                INSERT INTO post_analysis (post_id, summary_ru, metadata_json, created_at, updated_at)
                VALUES (:postId, :summary, :metadataJson, NOW(), NOW())
                """)
                .bind("postId", postId)
                .bind("summary", summary)
                .bind("metadataJson", objectMapper.writeValueAsString(metadata))
                .then()
                .block();
    }

    private String queryForString(String sql) {
        return databaseClient
                .sql(sql)
                .map((row, metadata) -> row.get(0, String.class))
                .one()
                .block();
    }

    private OffsetDateTime utc(String value) {
        return OffsetDateTime.parse(value).withOffsetSameInstant(ZoneOffset.UTC);
    }

    private PayloadBuilder settingsPayload() {
        return new PayloadBuilder()
                .with("daily_digest_time", "08:45")
                .with("weekly_digest_day_of_week", "fri")
                .with("weekly_digest_time", "16:30")
                .with("recipient_email", "reader@example.com")
                .with("sender_identity", "Good News Digest <digest@example.com>")
                .with("smtp_host", "smtp.example.com")
                .with("smtp_port", 465)
                .with("smtp_username", "digest-user")
                .with("smtp_security_mode", "ssl")
                .with("daily_digest_enabled", true)
                .with("daily_digest_catch_up_enabled", false)
                .with("weekly_digest_enabled", true)
                .with("weekly_digest_catch_up_enabled", false);
    }

    @TestConfiguration
    static class TestSmtpConfiguration {

        @Bean
        @Primary
        RecordingSmtpEmailAdapter recordingSmtpEmailAdapter() {
            return new RecordingSmtpEmailAdapter();
        }
    }

    static class RecordingSmtpEmailAdapter implements SmtpEmailAdapter {

        private final AtomicReference<TestEmailMessage> message = new AtomicReference<>();
        private final AtomicReference<SmtpConnectionSettings> connectionSettings = new AtomicReference<>();
        private final AtomicReference<String> threadName = new AtomicReference<>();
        private final AtomicReference<Boolean> nonBlockingThread = new AtomicReference<>();

        @Override
        public void send(TestEmailMessage message, SmtpConnectionSettings connectionSettings) {
            this.message.set(message);
            this.connectionSettings.set(connectionSettings);
            this.threadName.set(Thread.currentThread().getName());
            this.nonBlockingThread.set(reactor.core.scheduler.Schedulers.isInNonBlockingThread());
        }

        void reset() {
            message.set(null);
            connectionSettings.set(null);
            threadName.set(null);
            nonBlockingThread.set(null);
        }

        TestEmailMessage message() {
            return message.get();
        }

        SmtpConnectionSettings connectionSettings() {
            return connectionSettings.get();
        }

        String threadName() {
            return threadName.get();
        }

        Boolean nonBlockingThread() {
            return nonBlockingThread.get();
        }
    }

    private static final class PayloadBuilder {

        private final Map<String, Object> values = new LinkedHashMap<>();

        private PayloadBuilder with(String key, Object value) {
            values.put(key, value);
            return this;
        }

        private Map<String, Object> build() {
            return values;
        }
    }
}
