package com.goodnews.backendjava.ingestion.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.goodnews.backendjava.ingestion.application.port.SourceReader;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class SyncActiveSourcesTest {
    @Test
    void aggregatesPartialFailuresWithoutChangingTheOrderedSuccessfulIds() {
        SyncSingleSource singleSource = Mockito.mock(SyncSingleSource.class);
        Mockito.when(singleSource.sync(1L)).thenReturn(Mono.just(SyncOutcome.success(1L)));
        Mockito.when(singleSource.sync(2L)).thenReturn(Mono.just(SyncOutcome.failure()));
        Mockito.when(singleSource.sync(3L)).thenReturn(Mono.just(SyncOutcome.success(3L)));

        StepVerifier.create(new SyncActiveSources(reader(1L, 2L, 3L), singleSource, 2).sync())
                .assertNext(outcome -> assertThat(outcome.processedSourceIds()).containsExactly(1L, 3L))
                .verifyComplete();
    }

    @Test
    void subscribesToNoMoreThanTheConfiguredConcurrencyAndEmitsSourceOrder() {
        AtomicInteger active = new AtomicInteger();
        AtomicInteger maximum = new AtomicInteger();
        SyncSingleSource singleSource = Mockito.mock(SyncSingleSource.class);
        for (long id = 1; id <= 5; id++) {
            long sourceId = id;
            Mockito.when(singleSource.sync(sourceId))
                    .thenAnswer(invocation -> Mono.defer(() -> {
                        int current = active.incrementAndGet();
                        maximum.accumulateAndGet(current, Math::max);
                        return Mono.delay(java.time.Duration.ofMillis(10))
                                .thenReturn(SyncOutcome.success(sourceId))
                                .doOnTerminate(active::decrementAndGet);
                    }));
        }

        StepVerifier.create(new SyncActiveSources(reader(1L, 2L, 3L, 4L, 5L), singleSource, 2).sync())
                .assertNext(outcome -> assertThat(outcome.processedSourceIds()).containsExactly(1L, 2L, 3L, 4L, 5L))
                .verifyComplete();

        assertThat(maximum.get()).isLessThanOrEqualTo(2);
    }

    private static SourceReader reader(long... ids) {
        return new SourceReader() {
            @Override
            public Mono<com.goodnews.backendjava.ingestion.model.SourceDefinition> find(long sourceId) {
                return Mono.empty();
            }

            @Override
            public Flux<Long> findActiveIdsOrdered() {
                return Flux.fromStream(java.util.Arrays.stream(ids).boxed());
            }
        };
    }
}
