package com.goodnews.backendjava.analysis.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.goodnews.backendjava.analysis.application.port.AnalysisClient;
import com.goodnews.backendjava.analysis.application.port.AnalysisContextQuery;
import com.goodnews.backendjava.analysis.application.port.AnalysisRepository;
import com.goodnews.backendjava.analysis.model.AnalysisContext;
import com.goodnews.backendjava.analysis.model.AnalysisRequest;
import com.goodnews.backendjava.analysis.model.AnalysisResult;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class AnalyzePendingPostsTest {
    @Test
    void limitsRunToTwentyUsesSequentialChunksAndReportsExactCounts() {
        FakeRepository repository = new FakeRepository(25);
        AtomicInteger contexts = new AtomicInteger();
        List<List<Long>> chunks = new ArrayList<>();
        AnalysisClient client = (requests, context) -> {
            chunks.add(requests.stream().map(AnalysisRequest::postId).toList());
            return Mono.just(
                    requests.stream().map(AnalyzePendingPostsTest::result).toList());
        };
        AnalyzePendingPosts useCase = new AnalyzePendingPosts(
                repository,
                () -> {
                    contexts.incrementAndGet();
                    return Mono.just(new AnalysisContext("summary", "reason", "profile"));
                },
                client,
                7);

        StepVerifier.create(useCase.execute())
                .assertNext(outcome -> {
                    assertThat(outcome.analyzed()).isEqualTo(20);
                    assertThat(outcome.remaining()).isEqualTo(5);
                })
                .verifyComplete();

        assertThat(chunks).extracting(List::size).containsExactly(7, 7, 6);
        assertThat(contexts).hasValue(1);
    }

    @Test
    void lastDuplicateWinsMissingItemsStayPendingAndLaterChunkContinues() {
        FakeRepository repository = new FakeRepository(5);
        AtomicInteger chunk = new AtomicInteger();
        AnalysisClient client = (requests, context) -> {
            if (chunk.getAndIncrement() == 0) {
                return Mono.just(List.of(result(requests.getFirst()), result(requests.getFirst())));
            }
            return Mono.just(List.of(result(requests.getFirst())));
        };
        AnalyzePendingPosts useCase = new AnalyzePendingPosts(repository, context(), client, 3);

        StepVerifier.create(useCase.execute())
                .assertNext(outcome -> {
                    assertThat(outcome.analyzed()).isEqualTo(2);
                    assertThat(outcome.remaining()).isEqualTo(3);
                })
                .verifyComplete();
        assertThat(chunk).hasValue(2);
    }

    @Test
    void outcomeUsesPythonBeforeMinusRemainingSemanticsDuringConcurrentInsertion() {
        FakeRepository repository = new FakeRepository(3);
        repository.insertAfterSave = true;
        AnalysisClient client = (requests, context) -> Mono.just(List.of(result(requests.getFirst())));

        StepVerifier.create(new AnalyzePendingPosts(repository, context(), client, 3).execute())
                .assertNext(outcome -> {
                    assertThat(outcome.analyzed()).isZero();
                    assertThat(outcome.remaining()).isEqualTo(3);
                })
                .verifyComplete();
    }

    @Test
    void failedChunkDoesNotStopFollowingChunkAndEmptyQueueSkipsContext() {
        FakeRepository repository = new FakeRepository(4);
        AtomicInteger calls = new AtomicInteger();
        AnalysisClient client = (requests, context) -> calls.getAndIncrement() == 0
                ? Mono.error(new IllegalStateException("failed"))
                : Mono.just(
                        requests.stream().map(AnalyzePendingPostsTest::result).toList());
        AnalyzePendingPosts useCase = new AnalyzePendingPosts(repository, context(), client, 2);

        StepVerifier.create(useCase.execute())
                .assertNext(outcome -> assertThat(outcome.analyzed()).isEqualTo(2))
                .verifyComplete();
        assertThat(calls).hasValue(2);

        AtomicInteger contexts = new AtomicInteger();
        AnalyzePendingPosts empty = new AnalyzePendingPosts(
                new FakeRepository(0),
                () -> {
                    contexts.incrementAndGet();
                    return Mono.just(new AnalysisContext("", "", ""));
                },
                client,
                2);
        StepVerifier.create(empty.execute())
                .assertNext(outcome -> assertThat(outcome.remaining()).isZero())
                .verifyComplete();
        assertThat(contexts).hasValue(0);
    }

    private static AnalysisContextQuery context() {
        return () -> Mono.just(new AnalysisContext("summary", "reason", ""));
    }

    private static AnalysisResult result(AnalysisRequest request) {
        return result(request.postId());
    }

    private static AnalysisResult result(long id) {
        return new AnalysisResult(id, "Резюме", List.of("Java"), "tutorial", "advanced", "interesting", "Useful", 8);
    }

    private static final class FakeRepository implements AnalysisRepository {
        private final List<AnalysisRequest> pending = new ArrayList<>();
        private boolean insertAfterSave;

        private FakeRepository(int count) {
            for (long id = 1; id <= count; id++) {
                pending.add(new AnalysisRequest(id, "Post " + id, "Body"));
            }
        }

        @Override
        public Flux<AnalysisRequest> findPending(int limit) {
            return Flux.fromIterable(pending.stream().limit(limit).toList());
        }

        @Override
        public Mono<Void> saveResults(List<AnalysisResult> results) {
            Set<Long> saved =
                    new HashSet<>(results.stream().map(AnalysisResult::postId).toList());
            pending.removeIf(request -> saved.contains(request.postId()));
            if (insertAfterSave) {
                pending.add(new AnalysisRequest(999, "Concurrent", "Body"));
                insertAfterSave = false;
            }
            return Mono.empty();
        }

        @Override
        public Mono<Integer> countPending() {
            return Mono.just(pending.size());
        }
    }
}
