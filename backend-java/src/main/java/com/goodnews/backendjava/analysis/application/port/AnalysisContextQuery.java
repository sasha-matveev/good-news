package com.goodnews.backendjava.analysis.application.port;

import com.goodnews.backendjava.analysis.model.AnalysisContext;
import reactor.core.publisher.Mono;

public interface AnalysisContextQuery {
    Mono<AnalysisContext> load();
}
