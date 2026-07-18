package com.goodnews.backendjava.jobs;

import com.goodnews.backendjava.analysis.application.AnalyzePendingPosts;
import com.goodnews.backendjava.api.dto.InternalJobDtos;
import com.goodnews.backendjava.ingestion.application.SyncActiveSources;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

@Service
public final class SourceSyncJob {
    private static final Logger LOGGER = LoggerFactory.getLogger(SourceSyncJob.class);

    private final SyncActiveSources sourceSync;
    private final ObjectProvider<AnalyzePendingPosts> analysis;

    public SourceSyncJob(SyncActiveSources sourceSync, ObjectProvider<AnalyzePendingPosts> analysis) {
        this.sourceSync = sourceSync;
        this.analysis = analysis;
    }

    public Mono<InternalJobDtos.SourceSyncJobResponse> run() {
        return sourceSync.sync().flatMap(outcome -> analyzePending()
                .map(analyzed -> new InternalJobDtos.SourceSyncJobResponse(
                        List.copyOf(outcome.processedSourceIds()), analyzed)));
    }

    private Mono<Boolean> analyzePending() {
        AnalyzePendingPosts analyzer = analysis.getIfAvailable();
        if (analyzer == null) {
            LOGGER.warn("source-sync job: analysis client is not configured");
            return Mono.just(false);
        }
        return analyzer.execute().thenReturn(true).onErrorResume(error -> {
            LOGGER.error("source-sync job: analyze_pending_posts failed", error);
            return Mono.just(false);
        });
    }
}
