package com.goodnews.backendjava.config;

import java.util.UUID;
import java.util.regex.Pattern;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public final class BackendIdentityWebFilter implements WebFilter {
    static final String BACKEND_HEADER = "X-Good-News-Backend";
    static final String CORRELATION_HEADER = "X-Correlation-ID";
    static final String BACKEND_IDENTITY = "java";

    private static final Pattern SAFE_CORRELATION_ID = Pattern.compile("^[A-Za-z0-9._:-]{1,128}$");

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        String correlationId = correlationId(exchange.getRequest().getHeaders().getFirst(CORRELATION_HEADER));
        exchange.getResponse().getHeaders().set(BACKEND_HEADER, BACKEND_IDENTITY);
        exchange.getResponse().getHeaders().set(CORRELATION_HEADER, correlationId);
        return chain.filter(exchange);
    }

    private String correlationId(String candidate) {
        String normalized = candidate == null ? "" : candidate.strip();
        return SAFE_CORRELATION_ID.matcher(normalized).matches()
                ? normalized
                : UUID.randomUUID().toString();
    }
}
