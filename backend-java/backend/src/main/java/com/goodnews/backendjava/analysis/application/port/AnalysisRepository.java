package com.goodnews.backendjava.analysis.application.port;

import com.goodnews.backendjava.analysis.model.AnalysisRequest;
import com.goodnews.backendjava.analysis.model.AnalysisResult;
import java.util.List;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface AnalysisRepository {
    Flux<AnalysisRequest> findPending(int limit);

    Mono<Void> saveResults(List<AnalysisResult> results);

    Mono<Integer> countPending();
}
