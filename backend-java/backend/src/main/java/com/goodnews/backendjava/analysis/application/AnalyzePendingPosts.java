package com.goodnews.backendjava.analysis.application;

import com.goodnews.backendjava.analysis.application.port.AnalysisClient;
import com.goodnews.backendjava.analysis.application.port.AnalysisContextQuery;
import com.goodnews.backendjava.analysis.application.port.AnalysisRepository;
import com.goodnews.backendjava.analysis.model.AnalysisContext;
import com.goodnews.backendjava.analysis.model.AnalysisRequest;
import com.goodnews.backendjava.analysis.model.AnalysisResult;
import com.goodnews.backendjava.analysis.model.AnalyzePendingOutcome;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public final class AnalyzePendingPosts {
    private static final Logger LOGGER = LoggerFactory.getLogger(AnalyzePendingPosts.class);
    private static final int RUN_LIMIT = 20;

    private final AnalysisRepository repository;
    private final AnalysisContextQuery contextQuery;
    private final AnalysisClient client;
    private final int chunkSize;

    public AnalyzePendingPosts(
            AnalysisRepository repository, AnalysisContextQuery contextQuery, AnalysisClient client, int chunkSize) {
        this.repository = repository;
        this.contextQuery = contextQuery;
        this.client = client;
        this.chunkSize = chunkSize;
    }

    public Mono<AnalyzePendingOutcome> execute() {
        return repository.countPending().flatMap(before -> repository
                .findPending(RUN_LIMIT)
                .collectList()
                .flatMap(requests -> {
                    if (requests.isEmpty()) {
                        return Mono.just(new AnalyzePendingOutcome(0, before));
                    }
                    return contextQuery
                            .load()
                            .flatMap(context -> process(requests, context))
                            .then(Mono.defer(repository::countPending))
                            .map(remaining -> new AnalyzePendingOutcome(Math.max(0, before - remaining), remaining));
                }));
    }

    private Mono<Integer> process(List<AnalysisRequest> requests, AnalysisContext context) {
        return Flux.fromIterable(partition(requests))
                .concatMap(chunk -> client.analyze(chunk, context)
                        .map(results -> validResults(chunk, results))
                        .flatMap(results -> repository.saveResults(results).thenReturn(results.size()))
                        .onErrorResume(error -> {
                            LOGGER.warn(
                                    "Analysis chunk failed for post ids {}",
                                    chunk.stream().map(AnalysisRequest::postId).toList(),
                                    error);
                            return Mono.just(0);
                        }))
                .reduce(0, Integer::sum);
    }

    private List<List<AnalysisRequest>> partition(List<AnalysisRequest> requests) {
        return java.util.stream.IntStream.iterate(0, start -> start < requests.size(), start -> start + chunkSize)
                .mapToObj(start -> requests.subList(start, Math.min(requests.size(), start + chunkSize)))
                .toList();
    }

    private List<AnalysisResult> validResults(List<AnalysisRequest> chunk, List<AnalysisResult> results) {
        Set<Long> expected = chunk.stream().map(AnalysisRequest::postId).collect(java.util.stream.Collectors.toSet());
        Map<Long, AnalysisResult> byId = new LinkedHashMap<>();
        for (AnalysisResult result : results) {
            if (expected.contains(result.postId())) {
                byId.put(result.postId(), result);
            }
        }
        return List.copyOf(byId.values());
    }
}
