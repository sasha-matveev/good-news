package com.goodnews.backendjava.analysis.infrastructure;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.goodnews.backendjava.analysis.application.AnalyzePendingPosts;
import com.goodnews.backendjava.analysis.application.port.AnalysisClient;
import com.goodnews.backendjava.analysis.application.port.AnalysisContextQuery;
import com.goodnews.backendjava.analysis.application.port.AnalysisRepository;
import com.goodnews.backendjava.analysis.infrastructure.gemini.GeminiAnalysisClient;
import com.goodnews.backendjava.analysis.infrastructure.gemini.ReactiveRequestRateLimiter;
import com.goodnews.backendjava.analysis.infrastructure.gemini.StubAnalysisClient;
import com.goodnews.backendjava.config.GeminiProperties;
import com.goodnews.backendjava.config.GoodNewsProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Condition;
import org.springframework.context.annotation.ConditionContext;
import org.springframework.context.annotation.Conditional;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.type.AnnotatedTypeMetadata;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
public class AnalysisConfiguration {
    @Bean
    @Conditional(AnalysisConfigured.class)
    AnalysisClient analysisClient(
            GoodNewsProperties properties, WebClient.Builder webClientBuilder, ObjectMapper objectMapper) {
        return client(properties, webClientBuilder, objectMapper);
    }

    @Bean
    @Conditional(AnalysisConfigured.class)
    AnalyzePendingPosts analyzePendingPosts(
            AnalysisRepository repository,
            AnalysisContextQuery contextQuery,
            AnalysisClient client,
            GoodNewsProperties properties) {
        return new AnalyzePendingPosts(
                repository, contextQuery, client, properties.gemini().batchSize());
    }

    private AnalysisClient client(
            GoodNewsProperties properties, WebClient.Builder webClientBuilder, ObjectMapper objectMapper) {
        String stub = properties.app().analysisStubResponseJson();
        if (hasText(stub)) {
            return new StubAnalysisClient(stub, objectMapper);
        }
        GeminiProperties gemini = properties.gemini();
        return new GeminiAnalysisClient(
                webClientBuilder,
                objectMapper,
                new ReactiveRequestRateLimiter(gemini.maxRpm()),
                gemini.apiKey(),
                gemini.model(),
                gemini.maxRetries());
    }

    private static boolean hasText(String value) {
        return value != null && !value.isBlank();
    }
}

final class AnalysisConfigured implements Condition {
    @Override
    public boolean matches(ConditionContext context, AnnotatedTypeMetadata metadata) {
        String stub = context.getEnvironment().getProperty("good-news.app.analysis-stub-response-json");
        String key = context.getEnvironment().getProperty("good-news.gemini.api-key");
        return (stub != null && !stub.isBlank()) || (key != null && !key.isBlank());
    }
}
