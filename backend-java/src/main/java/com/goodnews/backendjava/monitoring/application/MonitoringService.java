package com.goodnews.backendjava.monitoring.application;

import com.goodnews.backendjava.monitoring.application.port.MonitoringQuery;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Service
public final class MonitoringService {
    private final MonitoringQuery queries;

    public MonitoringService(MonitoringQuery queries) {
        this.queries = queries;
    }

    public Mono<MonitoringSummary> summary() {
        return queries.summary();
    }

    public Flux<MonitoringQueueItem> queue() {
        return queries.queue();
    }
}
