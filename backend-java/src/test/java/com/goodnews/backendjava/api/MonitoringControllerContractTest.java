package com.goodnews.backendjava.api;

import com.goodnews.backendjava.analysis.application.AnalyzePendingPosts;
import com.goodnews.backendjava.api.contract.ApiErrorHandler;
import com.goodnews.backendjava.monitoring.application.MonitoringQueueItem;
import com.goodnews.backendjava.monitoring.application.MonitoringService;
import com.goodnews.backendjava.monitoring.application.MonitoringSummary;
import com.goodnews.backendjava.monitoring.application.port.MonitoringQuery;
import java.time.Instant;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.support.DefaultListableBeanFactory;
import org.springframework.test.web.reactive.server.WebTestClient;

class MonitoringControllerContractTest {
    @Test
    void analyzeNowReportsTheUnavailableAnalysisRuntime() {
        MonitoringQuery queries = new MonitoringQuery() {
            public reactor.core.publisher.Mono<MonitoringSummary> summary() {
                return reactor.core.publisher.Mono.empty();
            }

            public reactor.core.publisher.Flux<MonitoringQueueItem> queue() {
                return reactor.core.publisher.Flux.empty();
            }
        };
        WebTestClient.bindToController(new MonitoringController(service(queries)))
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
    }

    @Test
    void summaryAndQueueKeepThePythonMonitoringContracts() {
        MonitoringQuery queries = new MonitoringQuery() {
            @Override
            public reactor.core.publisher.Mono<MonitoringSummary> summary() {
                return reactor.core.publisher.Mono.just(new MonitoringSummary(
                        2,
                        3,
                        8,
                        5,
                        Instant.parse("2026-07-13T10:15:30Z"),
                        Map.of("content_api", "ok", "analysis_llm", "ok")));
            }

            @Override
            public reactor.core.publisher.Flux<MonitoringQueueItem> queue() {
                return reactor.core.publisher.Flux.just(
                        new MonitoringQueueItem(17, "Queued post", "Source", Instant.parse("2026-07-13T09:00:00Z")));
            }
        };
        WebTestClient client = WebTestClient.bindToController(new MonitoringController(service(queries)))
                .controllerAdvice(new ApiErrorHandler())
                .build();

        client.get()
                .uri("/api/monitoring/summary")
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .json(
                        """
                        {"sources_active":2,"sources_total":3,"posts_total":8,"posts_unranked":5,
                        "last_sync_at":"2026-07-13T10:15:30Z","services":{"content_api":"ok","analysis_llm":"ok"}}
                        """);
        client.get()
                .uri("/api/monitoring/queue")
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .json(
                        """
                        [{"post_id":17,"title":"Queued post","source_name":"Source","created_at":"2026-07-13T09:00:00Z"}]
                        """);
    }

    private MonitoringService service(MonitoringQuery queries) {
        return new MonitoringService(
                queries, new DefaultListableBeanFactory().getBeanProvider(AnalyzePendingPosts.class));
    }
}
