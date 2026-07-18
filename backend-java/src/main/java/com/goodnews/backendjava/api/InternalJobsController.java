package com.goodnews.backendjava.api;

import com.goodnews.backendjava.api.dto.InternalJobDtos;
import com.goodnews.backendjava.jobs.ScheduledDigestJobs;
import com.goodnews.backendjava.jobs.SourceSyncJob;
import java.time.Clock;
import java.time.Instant;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

@RestController
public final class InternalJobsController {
    private final SourceSyncJob sourceSync;
    private final ScheduledDigestJobs digests;
    private final Clock clock;

    public InternalJobsController(SourceSyncJob sourceSync, ScheduledDigestJobs digests, Clock clock) {
        this.sourceSync = sourceSync;
        this.digests = digests;
        this.clock = clock;
    }

    @PostMapping("/internal/jobs/source-sync")
    public Mono<InternalJobDtos.SourceSyncJobResponse> sourceSync() {
        return sourceSync.run();
    }

    @PostMapping("/internal/jobs/digests")
    public Mono<InternalJobDtos.DigestJobResponse> digests() {
        return digests.runDue(clock.instant()).map(this::response);
    }

    private InternalJobDtos.DigestJobResponse response(ScheduledDigestJobs.RunResult result) {
        return new InternalJobDtos.DigestJobResponse(
                iso(result.dailyRanFor()),
                iso(result.weeklyRanFor()),
                iso(result.observabilityRanFor()),
                result.errors());
    }

    private String iso(Instant value) {
        return value == null ? null : value.toString();
    }
}
