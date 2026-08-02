package com.goodnews.backendjava.analysis.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

import com.goodnews.backendjava.analysis.application.AnalyzePendingPosts;
import com.goodnews.backendjava.analysis.application.port.AnalysisClient;
import com.goodnews.backendjava.analysis.application.port.AnalysisContextQuery;
import com.goodnews.backendjava.analysis.application.port.AnalysisRepository;
import com.goodnews.backendjava.analysis.infrastructure.gemini.GeminiAnalysisClient;
import com.goodnews.backendjava.analysis.infrastructure.gemini.StubAnalysisClient;
import com.goodnews.backendjava.api.MonitoringController;
import com.goodnews.backendjava.api.contract.ApiErrorHandler;
import com.goodnews.backendjava.config.AppProperties;
import com.goodnews.backendjava.config.AuthProperties;
import com.goodnews.backendjava.config.DatabaseProperties;
import com.goodnews.backendjava.config.EmailProperties;
import com.goodnews.backendjava.config.GeminiProperties;
import com.goodnews.backendjava.config.GoodNewsProperties;
import com.goodnews.backendjava.config.SchedulerProperties;
import com.goodnews.backendjava.monitoring.application.MonitoringService;
import com.goodnews.backendjava.monitoring.application.port.MonitoringQuery;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.springframework.web.reactive.function.client.WebClient;
import tools.jackson.databind.ObjectMapper;

class AnalysisConfigurationTest {
    private static final String STUB =
            """
            {"summary_ru":"Резюме","topics":[],"format":"news","technical_depth":"beginner",
            "verdict":"interesting","verdict_reason":"Useful","relevance_score":7}
            """;

    @Test
    void stubWinsOverKey() {
        runner(STUB, "key")
                .withPropertyValues("good-news.app.analysis-stub-response-json=" + STUB, "good-news.gemini.api-key=key")
                .run(context ->
                        assertThat(context.getBean(AnalysisClient.class)).isInstanceOf(StubAnalysisClient.class));
    }

    @Test
    void keyOnlyWiresConfiguredGeminiAndUseCaseValues() {
        runner(null, "key").withPropertyValues("good-news.gemini.api-key=key").run(context -> {
            GeminiAnalysisClient client = context.getBean(GeminiAnalysisClient.class);
            assertThat(ReflectionTestUtils.getField(client, "model")).isEqualTo("configured-model");
            assertThat(ReflectionTestUtils.getField(client, "maxAttempts")).isEqualTo(6);
            assertThat(ReflectionTestUtils.getField(client, "responseTimeout")).isEqualTo(Duration.ofSeconds(60));
            Object limiter = ReflectionTestUtils.getField(client, "limiter");
            assertThat(ReflectionTestUtils.getField(limiter, "intervalNanos"))
                    .isEqualTo(Duration.ofMinutes(1).toNanos() / 13);
            assertThat(ReflectionTestUtils.getField(context.getBean(AnalyzePendingPosts.class), "chunkSize"))
                    .isEqualTo(4);
        });
    }

    @Test
    void neitherProviderOmitsUseCaseAndControllerKeepsExact503() {
        runner(null, null).run(context -> {
            assertThat(context).doesNotHaveBean(AnalysisClient.class).doesNotHaveBean(AnalyzePendingPosts.class);
            MonitoringService service = new MonitoringService(
                    mock(MonitoringQuery.class), context.getBeanProvider(AnalyzePendingPosts.class));
            WebTestClient.bindToController(new MonitoringController(service))
                    .controllerAdvice(new ApiErrorHandler())
                    .build()
                    .post()
                    .uri("/api/monitoring/analyze-now")
                    .exchange()
                    .expectStatus()
                    .isEqualTo(503)
                    .expectBody()
                    .jsonPath("$.detail")
                    .isEqualTo("Analysis client is not configured in this runtime.");
        });
    }

    private ApplicationContextRunner runner(String stub, String key) {
        return new ApplicationContextRunner()
                .withUserConfiguration(AnalysisConfiguration.class)
                .withBean(AnalysisRepository.class, () -> mock(AnalysisRepository.class))
                .withBean(AnalysisContextQuery.class, () -> mock(AnalysisContextQuery.class))
                .withBean(WebClient.Builder.class, WebClient::builder)
                .withBean(ObjectMapper.class, ObjectMapper::new)
                .withBean(GoodNewsProperties.class, () -> properties(stub, key));
    }

    private GoodNewsProperties properties(String stub, String key) {
        return new GoodNewsProperties(
                new AppProperties(
                        "test",
                        "localhost",
                        8000,
                        5173,
                        "localhost",
                        8100,
                        "localhost",
                        8200,
                        "localhost",
                        8300,
                        stub,
                        null),
                new DatabaseProperties(null, "localhost", 5432, "good_news", "good_news", null),
                new AuthProperties(null, "", null),
                new SchedulerProperties(30, 3, null),
                new GeminiProperties(key, "configured-model", 4, 13, 6),
                new EmailProperties(null, null, null));
    }
}
