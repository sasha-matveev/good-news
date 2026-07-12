package com.goodnews.backendjava.ingestion.application.port;

import com.goodnews.backendjava.ingestion.model.CandidatePost;
import com.goodnews.backendjava.ingestion.model.SourceDefinition;
import java.time.Instant;
import java.util.List;
import reactor.core.publisher.Mono;

public interface SourceReloadWriter {
    Mono<ReloadWriteResult> replaceRecentPosts(
            SourceDefinition source, List<CandidatePost> candidates, Instant cutoff, Instant synchronizedAt);

    record ReloadWriteResult(int deleted, int reloaded) {}
}
