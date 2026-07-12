package com.goodnews.backendjava.ingestion.application;

import com.goodnews.backendjava.ingestion.application.port.SourceReader;
import com.goodnews.backendjava.ingestion.application.port.SourceReloadWriter;
import com.goodnews.backendjava.ingestion.model.CandidatePost;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

@Service
public final class ReloadSourcePosts {
    private static final Duration WINDOW = Duration.ofDays(60);
    private final SourceReader sources;
    private final SourceReloadWriter writer;
    private final com.goodnews.backendjava.ingestion.strategy.SourceIngestionStrategies strategies;
    private final Clock clock;

    public ReloadSourcePosts(
            SourceReader sources,
            SourceReloadWriter writer,
            com.goodnews.backendjava.ingestion.strategy.SourceIngestionStrategies strategies,
            Clock clock) {
        this.sources = sources;
        this.writer = writer;
        this.strategies = strategies;
        this.clock = clock;
    }

    public Mono<SourceReloadWriter.ReloadWriteResult> reload(long sourceId) {
        Instant now = clock.instant();
        Instant cutoff = now.minus(WINDOW);
        return sources.find(sourceId)
                .switchIfEmpty(Mono.error(new SourceNotFoundException(sourceId)))
                .flatMap(source -> strategies
                        .resolve(source.strategyKind())
                        .ingest(source)
                        .map(posts -> recent(posts, cutoff))
                        .flatMap(posts -> writer.replaceRecentPosts(source, posts, cutoff, now)));
    }

    private static List<CandidatePost> recent(List<CandidatePost> posts, Instant cutoff) {
        return posts.stream()
                .filter(post ->
                        post.publishedAt() == null || !post.publishedAt().isBefore(cutoff))
                .toList();
    }
}
