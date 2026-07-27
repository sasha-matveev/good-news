package com.goodnews.backendjava.analysis.infrastructure.gemini;

import com.goodnews.backendjava.analysis.application.port.AnalysisClient;
import com.goodnews.backendjava.analysis.model.AnalysisContext;
import com.goodnews.backendjava.analysis.model.AnalysisRequest;
import com.goodnews.backendjava.analysis.model.AnalysisResult;
import java.util.List;
import reactor.core.publisher.Mono;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

public final class StubAnalysisClient implements AnalysisClient {
    private final JsonNode payload;
    private final AnalysisPayloadNormalizer normalizer;

    public StubAnalysisClient(String json, ObjectMapper objectMapper) {
        try {
            this.payload = objectMapper.readTree(json);
            this.normalizer = new AnalysisPayloadNormalizer(objectMapper);
            normalizer.normalize(0, payload);
        } catch (JacksonException | IllegalArgumentException exception) {
            throw new IllegalArgumentException("GOOD_NEWS_ANALYSIS_STUB_RESPONSE_JSON is invalid", exception);
        }
    }

    @Override
    public Mono<List<AnalysisResult>> analyze(List<AnalysisRequest> requests, AnalysisContext context) {
        return Mono.fromSupplier(() -> requests.stream()
                .map(request -> normalizer.normalize(request.postId(), payload))
                .toList());
    }
}
