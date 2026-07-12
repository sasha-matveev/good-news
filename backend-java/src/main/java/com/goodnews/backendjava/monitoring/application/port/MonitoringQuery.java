package com.goodnews.backendjava.monitoring.application.port;

import com.goodnews.backendjava.monitoring.application.MonitoringQueueItem;
import com.goodnews.backendjava.monitoring.application.MonitoringSummary;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface MonitoringQuery {
    Mono<MonitoringSummary> summary();

    Flux<MonitoringQueueItem> queue();
}
