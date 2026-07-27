package com.goodnews.backendjava.analysis.application.port;

import com.goodnews.backendjava.analysis.model.AnalysisContext;
import com.goodnews.backendjava.analysis.model.AnalysisRequest;
import com.goodnews.backendjava.analysis.model.AnalysisResult;
import java.util.List;
import reactor.core.publisher.Mono;

public interface AnalysisClient {
    Mono<List<AnalysisResult>> analyze(List<AnalysisRequest> requests, AnalysisContext context);
}
