package com.goodnews.backendjava.ingestion.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.goodnews.backendjava.ingestion.application.port.SourceReader;
import com.goodnews.backendjava.ingestion.application.port.SourceReloadWriter;
import com.goodnews.backendjava.ingestion.model.CandidatePost;
import com.goodnews.backendjava.ingestion.model.PublicationDateSource;
import com.goodnews.backendjava.ingestion.model.SourceDefinition;
import com.goodnews.backendjava.ingestion.model.SourceStrategyKind;
import com.goodnews.backendjava.ingestion.model.SourceStrategyOptions;
import com.goodnews.backendjava.ingestion.strategy.SourceIngestionStrategies;
import com.goodnews.backendjava.ingestion.strategy.SourceIngestionStrategy;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Function;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class ReloadSourcePostsTest {
    private static final Instant NOW = Instant.parse("2026-07-13T12:00:00Z");
    private static final SourceDefinition SOURCE = new SourceDefinition(
            7,
            "https://source.test",
            "https://source.test/feed",
            SourceStrategyKind.FEED,
            SourceStrategyOptions.empty(),
            null);

    @Test
    void reloadUsesAnExactSixtyDayWindowAndDoesNotWriteWhenFetchingFails() {
        AtomicReference<List<CandidatePost>> written = new AtomicReference<>();
        SourceReloadWriter writer = (source, posts, cutoff, synchronizedAt) -> {
            written.set(posts);
            assertThat(cutoff).isEqualTo(NOW.minus(java.time.Duration.ofDays(60)));
            assertThat(synchronizedAt).isEqualTo(NOW);
            return Mono.just(new SourceReloadWriter.ReloadWriteResult(4, posts.size()));
        };
        CandidatePost atCutoff = post("at-cutoff", NOW.minus(java.time.Duration.ofDays(60)));
        CandidatePost beforeCutoff =
                post("before-cutoff", NOW.minus(java.time.Duration.ofDays(60)).minusSeconds(1));
        CandidatePost noDate = post("no-date", null);
        ReloadSourcePosts reload = reload(ignored -> Mono.just(List.of(atCutoff, beforeCutoff, noDate)), writer);

        StepVerifier.create(reload.reload(SOURCE.id()))
                .assertNext(result -> assertThat(result).isEqualTo(new SourceReloadWriter.ReloadWriteResult(4, 2)))
                .verifyComplete();
        assertThat(written.get()).containsExactly(atCutoff, noDate);

        ReloadSourcePosts failedReload =
                reload(ignored -> Mono.error(new SourceIngestionException("fetch failed")), writer);
        StepVerifier.create(failedReload.reload(SOURCE.id()))
                .expectError(SourceIngestionException.class)
                .verify();
        assertThat(written.get()).containsExactly(atCutoff, noDate);
    }

    private static ReloadSourcePosts reload(
            Function<SourceDefinition, Mono<List<CandidatePost>>> ingestion, SourceReloadWriter writer) {
        SourceIngestionStrategy strategy = new SourceIngestionStrategy() {
            @Override
            public SourceStrategyKind kind() {
                return SourceStrategyKind.FEED;
            }

            @Override
            public Mono<List<CandidatePost>> ingest(SourceDefinition source) {
                return ingestion.apply(source);
            }
        };
        SourceReader reader = new SourceReader() {
            @Override
            public Mono<SourceDefinition> find(long sourceId) {
                return Mono.just(SOURCE);
            }

            @Override
            public Flux<Long> findActiveIdsOrdered() {
                return Flux.empty();
            }
        };
        return new ReloadSourcePosts(
                reader, writer, new SourceIngestionStrategies(List.of(strategy)), Clock.fixed(NOW, ZoneOffset.UTC));
    }

    private static CandidatePost post(String suffix, Instant publishedAt) {
        return new CandidatePost(
                "https://post.test/" + suffix, suffix, publishedAt, "content", PublicationDateSource.NONE);
    }
}
