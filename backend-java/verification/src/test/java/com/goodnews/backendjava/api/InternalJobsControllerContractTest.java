package com.goodnews.backendjava.api;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.goodnews.backendjava.api.dto.InternalJobDtos;
import com.goodnews.backendjava.jobs.ScheduledDigestJobs;
import com.goodnews.backendjava.jobs.SourceSyncJob;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.reactive.server.WebTestClient;
import reactor.core.publisher.Mono;

class InternalJobsControllerContractTest {
    private static final Instant NOW = Instant.parse("2026-07-18T13:00:00Z");

    @Test
    void keepsSchedulerFacingResponseContracts() {
        SourceSyncJob sourceSync = mock(SourceSyncJob.class);
        ScheduledDigestJobs digests = mock(ScheduledDigestJobs.class);
        when(sourceSync.run()).thenReturn(Mono.just(new InternalJobDtos.SourceSyncJobResponse(List.of(3L, 7L), true)));
        when(digests.runDue(NOW))
                .thenReturn(Mono.just(new ScheduledDigestJobs.RunResult(
                        Instant.parse("2026-07-18T12:00:00Z"), null, List.of("weekly: SMTP down"))));
        WebTestClient client = WebTestClient.bindToController(
                        new InternalJobsController(sourceSync, digests, Clock.fixed(NOW, ZoneOffset.UTC)))
                .build();

        client.post()
                .uri("/internal/jobs/source-sync")
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .json("{\"processed_source_ids\":[3,7],\"analyzed_pending\":true}");
        client.post()
                .uri("/internal/jobs/digests")
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .json(
                        """
                        {"daily_ran_for":"2026-07-18T12:00:00Z","weekly_ran_for":null,
                         "errors":["weekly: SMTP down"]}
                        """);
    }
}
