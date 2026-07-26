package com.goodnews.backendjava.analysis.infrastructure.gemini;

import com.goodnews.backendjava.analysis.application.port.AnalysisClient;
import com.goodnews.backendjava.analysis.model.AnalysisContext;
import com.goodnews.backendjava.analysis.model.AnalysisRequest;
import com.goodnews.backendjava.analysis.model.AnalysisResult;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatusCode;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import reactor.netty.http.client.HttpClientRequest;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

public final class GeminiAnalysisClient implements AnalysisClient {
    private static final int CONTENT_SNIPPET_CHARS = 4000;
    private static final String BASE_URL = "https://generativelanguage.googleapis.com/v1beta";

    private final WebClient webClient;
    private final ObjectMapper objectMapper;
    private final AnalysisPayloadNormalizer normalizer;
    private final ReactiveRequestRateLimiter limiter;
    private final String apiKey;
    private final String model;
    private final int maxAttempts;
    private final String baseUrl;
    private final Duration responseTimeout;

    public GeminiAnalysisClient(
            WebClient.Builder builder,
            ObjectMapper objectMapper,
            ReactiveRequestRateLimiter limiter,
            String apiKey,
            String model,
            int maxAttempts) {
        this(builder, objectMapper, limiter, apiKey, model, maxAttempts, BASE_URL, Duration.ofSeconds(60));
    }

    GeminiAnalysisClient(
            WebClient.Builder builder,
            ObjectMapper objectMapper,
            ReactiveRequestRateLimiter limiter,
            String apiKey,
            String model,
            int maxAttempts,
            String baseUrl) {
        this(builder, objectMapper, limiter, apiKey, model, maxAttempts, baseUrl, Duration.ofSeconds(60));
    }

    GeminiAnalysisClient(
            WebClient.Builder builder,
            ObjectMapper objectMapper,
            ReactiveRequestRateLimiter limiter,
            String apiKey,
            String model,
            int maxAttempts,
            String baseUrl,
            Duration responseTimeout) {
        this.webClient = builder.build();
        this.objectMapper = objectMapper;
        this.normalizer = new AnalysisPayloadNormalizer(objectMapper);
        this.limiter = limiter;
        this.apiKey = apiKey;
        this.model = model;
        this.maxAttempts = maxAttempts;
        this.baseUrl = baseUrl;
        this.responseTimeout = responseTimeout;
    }

    @Override
    public Mono<List<AnalysisResult>> analyze(List<AnalysisRequest> requests, AnalysisContext context) {
        String prompt = prompt(requests, context);
        Map<String, Object> body = Map.of(
                "contents", List.of(Map.of("parts", List.of(Map.of("text", prompt)))),
                "generationConfig", Map.of("responseMimeType", "application/json", "temperature", 0.2));
        return generate(body, 1).map(text -> normalizeBatch(text, requests));
    }

    private Mono<String> generate(Map<String, Object> body, int attempt) {
        return limiter.acquire()
                .then(webClient
                        .post()
                        .uri(baseUrl + "/models/" + model + ":generateContent")
                        .header("x-goog-api-key", apiKey)
                        .httpRequest(request -> {
                            Object nativeRequest = request.getNativeRequest();
                            if (nativeRequest instanceof HttpClientRequest reactorRequest) {
                                reactorRequest.responseTimeout(responseTimeout);
                            }
                        })
                        .bodyValue(body)
                        .exchangeToMono(response -> response.statusCode().value() == 429
                                ? retry(response, body, attempt)
                                : response.statusCode().isError() ? error(response) : candidateText(response)));
    }

    private Mono<String> retry(ClientResponse response, Map<String, Object> body, int attempt) {
        if (attempt >= maxAttempts) {
            return error(response);
        }
        Duration delay = retryDelay(response, attempt);
        return response.releaseBody().then(Mono.delay(delay)).then(generate(body, attempt + 1));
    }

    private Duration retryDelay(ClientResponse response, int attempt) {
        String header = response.headers().asHttpHeaders().getFirst("Retry-After");
        if (header != null) {
            try {
                return Duration.ofMillis((long) (Double.parseDouble(header) * 1000));
            } catch (NumberFormatException ignored) {
                // Fall through to exponential delay.
            }
        }
        return Duration.ofSeconds(1L << attempt);
    }

    private Mono<String> error(ClientResponse response) {
        HttpStatusCode status = response.statusCode();
        return response.bodyToMono(String.class)
                .defaultIfEmpty("")
                .flatMap(body -> Mono.error(new GeminiHttpException(status.value(), body)));
    }

    private Mono<String> candidateText(ClientResponse response) {
        return response.bodyToMono(JsonNode.class).map(root -> {
            JsonNode text = root.path("candidates")
                    .path(0)
                    .path("content")
                    .path("parts")
                    .path(0)
                    .path("text");
            if (!text.isString()) {
                throw new IllegalArgumentException("Gemini response missing candidate text");
            }
            return text.stringValue();
        });
    }

    private List<AnalysisResult> normalizeBatch(String text, List<AnalysisRequest> requests) {
        try {
            JsonNode root = objectMapper.readTree(text);
            JsonNode results = root.get("results");
            if (!root.isObject() || results == null || !results.isArray()) {
                throw new IllegalArgumentException("Gemini batch response must contain a results array");
            }
            java.util.Set<Long> expected =
                    requests.stream().map(AnalysisRequest::postId).collect(java.util.stream.Collectors.toSet());
            Map<Long, AnalysisResult> normalized = new LinkedHashMap<>();
            results.forEach(entry -> {
                JsonNode id = entry.get("id");
                Long parsedId = resultId(id);
                if (entry.isObject() && parsedId != null && expected.contains(parsedId)) {
                    try {
                        normalized.put(parsedId, normalizer.normalize(parsedId, entry));
                    } catch (IllegalArgumentException ignored) {
                        // A malformed item remains pending without discarding valid siblings.
                    }
                }
            });
            return List.copyOf(normalized.values());
        } catch (tools.jackson.core.JacksonException exception) {
            throw new IllegalArgumentException("Gemini candidate text is not JSON", exception);
        }
    }

    private Long resultId(JsonNode id) {
        if (id == null || id.isBoolean() || id.isContainer()) {
            return null;
        }
        try {
            if (id.isNumber()) {
                return id.decimalValue().stripTrailingZeros().longValueExact();
            }
            return Long.parseLong(id.stringValue());
        } catch (ArithmeticException | NumberFormatException exception) {
            return null;
        }
    }

    private String prompt(List<AnalysisRequest> requests, AnalysisContext context) {
        StringBuilder articles = new StringBuilder();
        for (AnalysisRequest request : requests) {
            if (!articles.isEmpty()) {
                articles.append("\n\n");
            }
            articles.append("[id=")
                    .append(request.postId())
                    .append("]\nTitle: ")
                    .append(request.title())
                    .append("\nContent: ")
                    .append(
                            request.content(),
                            0,
                            Math.min(CONTENT_SNIPPET_CHARS, request.content().length()));
        }
        String preference = context.preferenceProfile().isBlank()
                ? ""
                : "READER PREFERENCE PROFILE — judge verdict and relevance_score for THIS reader:\n"
                        + context.preferenceProfile() + "\n\n";
        return """
                You are a JSON-only API. Analyze EVERY article below and return ONE JSON object. No explanation, no markdown.
                Return: {"results": [ {"id": <the id given for the article>, ...fields...}, ... ]}
                Echo back the exact id for each article. Include every id exactly once.
                JSON fields per article:
                  "summary_ru": %s
                  "verdict_reason": %s
                  "verdict": "interesting" if worth reading for this reader, otherwise "not_interesting".
                  "relevance_score": integer 0-10 — how well this article matches the reader preference profile above. 10 = a perfect match for what the reader wants; 0 = irrelevant or matches what the reader avoids. Judge for THIS reader, not a generic developer. When no profile is given, score by general value to a software developer.
                  "topics": array of 1-3 short English tags.
                  "format": one of tutorial|opinion|news|case-study|announcement|other.
                  "technical_depth": one of beginner|intermediate|advanced.
                %sArticles:
                %s"""
                .formatted(context.summaryInstructions(), context.verdictReasonInstructions(), preference, articles);
    }

    public static final class GeminiHttpException extends RuntimeException {
        private final int status;

        GeminiHttpException(int status, String body) {
            super("Gemini HTTP " + status + ": " + body);
            this.status = status;
        }

        public int status() {
            return status;
        }
    }
}
