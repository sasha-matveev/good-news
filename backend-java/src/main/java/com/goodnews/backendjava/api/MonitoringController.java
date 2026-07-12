package com.goodnews.backendjava.api;

import com.goodnews.backendjava.api.contract.ApiHttpException;
import com.goodnews.backendjava.api.dto.MonitoringDtos;
import com.goodnews.backendjava.monitoring.application.MonitoringQueueItem;
import com.goodnews.backendjava.monitoring.application.MonitoringService;
import com.goodnews.backendjava.monitoring.application.MonitoringSummary;
import java.time.Instant;
import java.time.format.DateTimeFormatter;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@RestController
public final class MonitoringController {
    private final MonitoringService service;

    public MonitoringController(MonitoringService service) {
        this.service = service;
    }

    @GetMapping("/api/monitoring/summary")
    public Mono<MonitoringDtos.MonitoringSummaryResponse> summary() {
        return service.summary().map(this::summaryResponse);
    }

    @GetMapping("/api/monitoring/queue")
    public Flux<MonitoringDtos.MonitoringQueueItemResponse> queue() {
        return service.queue().map(this::queueResponse);
    }

    @PostMapping("/api/monitoring/analyze-now")
    public Mono<MonitoringDtos.AnalyzeNowResponse> analyzeNow() {
        return Mono.error(new ApiHttpException(
                org.springframework.http.HttpStatus.SERVICE_UNAVAILABLE,
                "Analysis client is not configured in this runtime."));
    }

    private MonitoringDtos.MonitoringSummaryResponse summaryResponse(MonitoringSummary summary) {
        return new MonitoringDtos.MonitoringSummaryResponse(
                summary.sourcesActive(),
                summary.sourcesTotal(),
                summary.postsTotal(),
                summary.postsUnranked(),
                utc(summary.lastSyncAt()),
                summary.services());
    }

    private MonitoringDtos.MonitoringQueueItemResponse queueResponse(MonitoringQueueItem item) {
        return new MonitoringDtos.MonitoringQueueItemResponse(
                item.postId(), item.title(), item.sourceName(), utc(item.createdAt()));
    }

    private static String utc(Instant value) {
        return value == null ? null : DateTimeFormatter.ISO_INSTANT.format(value);
    }
}
