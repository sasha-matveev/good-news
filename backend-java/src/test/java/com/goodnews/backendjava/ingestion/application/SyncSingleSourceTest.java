package com.goodnews.backendjava.ingestion.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.goodnews.backendjava.ingestion.application.port.SourceReader;
import com.goodnews.backendjava.ingestion.application.port.SourceSyncWriter;
import com.goodnews.backendjava.ingestion.knownsite.ClaudeBlogParser;
import com.goodnews.backendjava.ingestion.model.CandidatePost;
import com.goodnews.backendjava.ingestion.model.SourceDefinition;
import com.goodnews.backendjava.ingestion.model.SourceStrategyKind;
import com.goodnews.backendjava.ingestion.model.SourceStrategyOptions;
import com.goodnews.backendjava.ingestion.parsing.PublicationDateParser;
import com.goodnews.backendjava.ingestion.strategy.SourceIngestionStrategies;
import com.goodnews.backendjava.ingestion.strategy.SourceIngestionStrategy;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class SyncSingleSourceTest {
    private static final Instant NOW = Instant.parse("2025-06-03T10:00:00Z");
    private static final SourceDefinition SOURCE = new SourceDefinition(
            7L,
            "https://example.com",
            "https://example.com/feed",
            SourceStrategyKind.FEED,
            SourceStrategyOptions.empty(),
            null);

    @Test
    void missingSourceIsNotRecordedAsIngestionFailure() {
        RecordingWriter writer = new RecordingWriter();
        SyncSingleSource useCase = useCase(reader(id -> Mono.empty()), source -> Mono.just(List.of()), writer);

        StepVerifier.create(useCase.sync(7L))
                .expectError(SourceNotFoundException.class)
                .verify();

        assertThat(writer.failed).isFalse();
    }

    @Test
    void expectedIngestionFailureRecordsFailure() {
        RecordingWriter writer = new RecordingWriter();
        SyncSingleSource useCase = useCase(
                reader(id -> Mono.just(SOURCE)),
                source -> Mono.error(new SourceIngestionException("unreadable")),
                writer);

        StepVerifier.create(useCase.sync(7L))
                .assertNext(outcome -> assertThat(outcome.processedSourceIds()).isEmpty())
                .verifyComplete();

        assertThat(writer.failed).isTrue();
    }

    @Test
    void programmingOrDatabaseFailurePropagatesWithoutChangingSourceFailureState() {
        RecordingWriter writer = new RecordingWriter();
        SyncSingleSource useCase = useCase(
                reader(id -> Mono.just(SOURCE)), source -> Mono.error(new IllegalStateException("bug")), writer);

        StepVerifier.create(useCase.sync(7L))
                .expectError(IllegalStateException.class)
                .verify();

        assertThat(writer.failed).isFalse();
    }

    @Test
    void malformedExternalListingHrefRecordsSourceFailure() {
        RecordingWriter writer = new RecordingWriter();
        SyncSingleSource useCase = useCase(
                reader(id -> Mono.just(SOURCE)),
                source -> {
                    new ClaudeBlogParser(new PublicationDateParser())
                            .parseListing("<article><a href='/blog/%zz'><h2>Broken</h2></a></article>");
                    return Mono.just(List.of());
                },
                writer);

        StepVerifier.create(useCase.sync(7L))
                .assertNext(outcome -> assertThat(outcome.processedSourceIds()).isEmpty())
                .verifyComplete();

        assertThat(writer.failed).isTrue();
    }

    private static SyncSingleSource useCase(SourceReader reader, Ingest ingest, RecordingWriter writer) {
        SourceIngestionStrategy strategy = new SourceIngestionStrategy() {
            @Override
            public SourceStrategyKind kind() {
                return SourceStrategyKind.FEED;
            }

            @Override
            public Mono<List<CandidatePost>> ingest(SourceDefinition source) {
                return ingest.apply(source);
            }
        };
        return new SyncSingleSource(
                reader, writer, new SourceIngestionStrategies(List.of(strategy)), Clock.fixed(NOW, ZoneOffset.UTC));
    }

    private static SourceReader reader(java.util.function.LongFunction<Mono<SourceDefinition>> find) {
        return new SourceReader() {
            @Override
            public Mono<SourceDefinition> find(long sourceId) {
                return find.apply(sourceId);
            }

            @Override
            public reactor.core.publisher.Flux<Long> findActiveIdsOrdered() {
                return reactor.core.publisher.Flux.empty();
            }
        };
    }

    @FunctionalInterface
    private interface Ingest {
        Mono<List<CandidatePost>> apply(SourceDefinition source);
    }

    private static final class RecordingWriter implements SourceSyncWriter {
        private boolean failed;

        @Override
        public Mono<Void> completeSuccessfulSync(
                SourceDefinition source, List<CandidatePost> posts, Instant synchronizedAt) {
            return Mono.empty();
        }

        @Override
        public Mono<Void> recordFailedSync(long sourceId, Instant failedAt) {
            failed = true;
            return Mono.empty();
        }
    }
}
