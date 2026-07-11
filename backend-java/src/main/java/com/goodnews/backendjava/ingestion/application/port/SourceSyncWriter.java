package com.goodnews.backendjava.ingestion.application.port;

import com.goodnews.backendjava.ingestion.model.CandidatePost;
import com.goodnews.backendjava.ingestion.model.SourceDefinition;
import java.time.Instant;
import java.util.List;
import reactor.core.publisher.Mono;

public interface SourceSyncWriter {
    Mono<Void> completeSuccessfulSync(SourceDefinition source, List<CandidatePost> posts, Instant synchronizedAt);

    Mono<Void> recordFailedSync(long sourceId, Instant failedAt);
}
