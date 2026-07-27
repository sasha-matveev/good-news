package com.goodnews.backendjava.jobs;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.goodnews.backendjava.analysis.application.AnalyzePendingPosts;
import com.goodnews.backendjava.analysis.model.AnalyzePendingOutcome;
import com.goodnews.backendjava.api.dto.InternalJobDtos;
import com.goodnews.backendjava.ingestion.application.SyncActiveSources;
import com.goodnews.backendjava.ingestion.application.SyncOutcome;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.support.DefaultListableBeanFactory;
import reactor.core.publisher.Mono;

class SourceSyncJobTest {
    @Test
    void analyzesAfterSuccessfulSync() {
        SyncActiveSources sync = mock(SyncActiveSources.class);
        AnalyzePendingPosts analysis = mock(AnalyzePendingPosts.class);
        when(sync.sync()).thenReturn(Mono.just(new SyncOutcome(List.of(2L, 5L))));
        when(analysis.execute()).thenReturn(Mono.just(new AnalyzePendingOutcome(3, 0)));

        InternalJobDtos.SourceSyncJobResponse response =
                new SourceSyncJob(sync, provider(analysis)).run().block();

        assertThat(response.processed_source_ids()).containsExactly(2L, 5L);
        assertThat(response.analyzed_pending()).isTrue();
    }

    @Test
    void analysisFailureDoesNotFailSuccessfulSync() {
        SyncActiveSources sync = mock(SyncActiveSources.class);
        AnalyzePendingPosts analysis = mock(AnalyzePendingPosts.class);
        when(sync.sync()).thenReturn(Mono.just(new SyncOutcome(List.of(2L))));
        when(analysis.execute()).thenReturn(Mono.error(new IllegalStateException("Gemini unavailable")));

        InternalJobDtos.SourceSyncJobResponse response =
                new SourceSyncJob(sync, provider(analysis)).run().block();

        assertThat(response.processed_source_ids()).containsExactly(2L);
        assertThat(response.analyzed_pending()).isFalse();
    }

    @Test
    void missingAnalysisRuntimeIsReportedWithoutFailingSync() {
        SyncActiveSources sync = mock(SyncActiveSources.class);
        when(sync.sync()).thenReturn(Mono.just(new SyncOutcome(List.of())));

        InternalJobDtos.SourceSyncJobResponse response =
                new SourceSyncJob(sync, provider(null)).run().block();

        assertThat(response.processed_source_ids()).isEmpty();
        assertThat(response.analyzed_pending()).isFalse();
    }

    private ObjectProvider<AnalyzePendingPosts> provider(AnalyzePendingPosts value) {
        DefaultListableBeanFactory beans = new DefaultListableBeanFactory();
        if (value != null) {
            beans.registerSingleton("analysis", value);
        }
        return beans.getBeanProvider(AnalyzePendingPosts.class);
    }
}
