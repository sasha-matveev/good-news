package com.goodnews.backendjava.monitoring.application;

import com.goodnews.backendjava.analysis.application.AnalyzePendingPosts;
import com.goodnews.backendjava.analysis.model.AnalyzePendingOutcome;
import com.goodnews.backendjava.monitoring.application.port.MonitoringQuery;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Service
public final class MonitoringService {
    private final MonitoringQuery queries;
    private final AnalyzePendingPosts analyzePendingPosts;

    public MonitoringService(MonitoringQuery queries, ObjectProvider<AnalyzePendingPosts> analyzePendingPosts) {
        this.queries = queries;
        this.analyzePendingPosts = analyzePendingPosts.getIfAvailable();
    }

    public Mono<MonitoringSummary> summary() {
        return queries.summary();
    }

    public Flux<MonitoringQueueItem> queue() {
        return queries.queue();
    }

    public Mono<AnalyzePendingOutcome> analyzeNow() {
        return analyzePendingPosts == null ? Mono.empty() : analyzePendingPosts.execute();
    }
}
