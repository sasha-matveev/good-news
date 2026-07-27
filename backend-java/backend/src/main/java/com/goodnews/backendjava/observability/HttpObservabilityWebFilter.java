package com.goodnews.backendjava.observability;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Pattern;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.HandlerMapping;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class HttpObservabilityWebFilter implements WebFilter {

    static final String BACKEND_HEADER = "X-Good-News-Backend";
    static final String CORRELATION_HEADER = "X-Correlation-ID";
    static final String BACKEND_IDENTITY = "java";

    private static final Pattern SAFE_CORRELATION_ID = Pattern.compile("^[A-Za-z0-9._:-]{1,128}$");
    private static final Logger LOGGER = LoggerFactory.getLogger(HttpObservabilityWebFilter.class);

    private final MeterRegistry meters;
    private final ObjectMapper objectMapper;

    public HttpObservabilityWebFilter(MeterRegistry meters, ObjectMapper objectMapper) {
        this.meters = meters;
        this.objectMapper = objectMapper;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        long startedAt = System.nanoTime();
        String correlationId = correlationId(exchange.getRequest().getHeaders().getFirst(CORRELATION_HEADER));
        exchange.getResponse().getHeaders().set(BACKEND_HEADER, BACKEND_IDENTITY);
        exchange.getResponse().getHeaders().set(CORRELATION_HEADER, correlationId);

        return chain.filter(exchange)
                .doOnSuccess(ignored -> record(exchange, correlationId, startedAt, null))
                .doOnError(error -> record(exchange, correlationId, startedAt, error));
    }

    private void record(ServerWebExchange exchange, String correlationId, long startedAt, Throwable error) {
        Duration duration = Duration.ofNanos(System.nanoTime() - startedAt);
        int status = status(exchange, error);
        String route = route(exchange);
        String method = exchange.getRequest().getMethod().name();
        String[] tags = {
            "backend", BACKEND_IDENTITY,
            "method", method,
            "route", route,
            "status", Integer.toString(status)
        };
        Counter.builder("good.news.http.server.requests")
                .tags(tags)
                .register(meters)
                .increment();
        Timer.builder("good.news.http.server.duration")
                .tags(tags)
                .register(meters)
                .record(duration);
        if (status >= 400) {
            Counter.builder("good.news.http.server.errors")
                    .tags(tags)
                    .register(meters)
                    .increment();
        }
        writeStructuredLog(correlationId, method, route, status, duration, error);
    }

    private int status(ServerWebExchange exchange, Throwable error) {
        HttpStatusCode status = exchange.getResponse().getStatusCode();
        if (status != null) {
            return status.value();
        }
        return error == null ? 200 : 500;
    }

    private String route(ServerWebExchange exchange) {
        Object route = exchange.getAttribute(HandlerMapping.BEST_MATCHING_PATTERN_ATTRIBUTE);
        return route == null ? exchange.getRequest().getPath().value() : route.toString();
    }

    private void writeStructuredLog(
            String correlationId, String method, String route, int status, Duration duration, Throwable error) {
        Map<String, Object> event = new LinkedHashMap<>();
        event.put("severity", status >= 500 ? "ERROR" : "INFO");
        event.put("event", "http_request");
        event.put("backend", BACKEND_IDENTITY);
        event.put("correlation_id", correlationId);
        event.put("method", method);
        event.put("route", route);
        event.put("status", status);
        event.put("duration_ms", duration.toNanos() / 1_000_000.0);
        if (error != null) {
            event.put("error_type", error.getClass().getSimpleName());
        }
        String json;
        try {
            json = objectMapper.writeValueAsString(event);
        } catch (JacksonException exception) {
            LOGGER.warn("Could not serialize HTTP request event", exception);
            return;
        }
        if (status >= 500) {
            LOGGER.error(json, error);
        } else {
            LOGGER.info(json);
        }
    }

    private String correlationId(String candidate) {
        String normalized = candidate == null ? "" : candidate.strip();
        return SAFE_CORRELATION_ID.matcher(normalized).matches()
                ? normalized
                : UUID.randomUUID().toString();
    }
}
