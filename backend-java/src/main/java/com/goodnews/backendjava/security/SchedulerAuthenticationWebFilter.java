package com.goodnews.backendjava.security;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.goodnews.backendjava.api.contract.ApiHttpException;
import com.goodnews.backendjava.config.GoodNewsProperties;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.Map;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.ReactiveSecurityContextHolder;
import org.springframework.security.core.context.SecurityContextImpl;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;

@Component
public class SchedulerAuthenticationWebFilter implements WebFilter {

    private final GoodNewsProperties properties;
    private final GoogleOidcTokenVerifier tokenVerifier;
    private final ObjectMapper objectMapper;

    public SchedulerAuthenticationWebFilter(
        GoodNewsProperties properties,
        GoogleOidcTokenVerifier tokenVerifier,
        ObjectMapper objectMapper
    ) {
        this.properties = properties;
        this.tokenVerifier = tokenVerifier;
        this.objectMapper = objectMapper;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        if (!requiresAuthentication(exchange)) {
            return chain.filter(exchange);
        }
        if (isBlank(properties.scheduler().invoker())) {
            return writeError(exchange, HttpStatus.SERVICE_UNAVAILABLE, "Scheduler invoker is not configured.");
        }
        String token;
        try {
            token = bearerToken(exchange);
        } catch (ApiHttpException exception) {
            return writeError(exchange, exception.getStatus(), exception.getMessage());
        }
        return tokenVerifier.verify(token)
            .onErrorResume(exception -> writeError(exchange, HttpStatus.UNAUTHORIZED, "Invalid token.").then(Mono.empty()))
            .flatMap(claims -> {
                String email = claims.email() == null ? "" : claims.email().toLowerCase(Locale.ROOT);
                String expected = properties.scheduler().invoker().toLowerCase(Locale.ROOT);
                if (!claims.emailVerified() || !email.equals(expected)) {
                    return writeError(exchange, HttpStatus.FORBIDDEN, "Not allowed.");
                }
                UsernamePasswordAuthenticationToken authentication =
                    UsernamePasswordAuthenticationToken.authenticated(email, token, null);
                SecurityContextImpl context = new SecurityContextImpl(authentication);
                return chain.filter(exchange)
                    .contextWrite(ReactiveSecurityContextHolder.withSecurityContext(Mono.just(context)));
            });
    }

    private boolean requiresAuthentication(ServerWebExchange exchange) {
        return !HttpMethod.OPTIONS.equals(exchange.getRequest().getMethod())
            && exchange.getRequest().getPath().value().startsWith("/internal/jobs/");
    }

    private String bearerToken(ServerWebExchange exchange) {
        String header = exchange.getRequest().getHeaders().getFirst(HttpHeaders.AUTHORIZATION);
        if (header == null || !header.startsWith("Bearer ")) {
            throw new ApiHttpException(HttpStatus.UNAUTHORIZED, "Missing bearer token.");
        }
        String token = header.substring("Bearer ".length()).trim();
        if (token.isEmpty()) {
            throw new ApiHttpException(HttpStatus.UNAUTHORIZED, "Missing bearer token.");
        }
        return token;
    }

    private boolean isBlank(String value) {
        return value == null || value.isBlank();
    }

    private Mono<Void> writeError(ServerWebExchange exchange, HttpStatus status, String detail) {
        exchange.getResponse().setStatusCode(status);
        exchange.getResponse().getHeaders().setContentType(MediaType.APPLICATION_JSON);
        byte[] payload = toJsonBytes(Map.of("detail", detail));
        DataBuffer buffer = exchange.getResponse().bufferFactory().wrap(payload);
        return exchange.getResponse().writeWith(Mono.just(buffer));
    }

    private byte[] toJsonBytes(Map<String, String> body) {
        try {
            return objectMapper.writeValueAsBytes(body);
        } catch (JsonProcessingException exception) {
            return ("{\"detail\":\"" + body.get("detail") + "\"}").getBytes(StandardCharsets.UTF_8);
        }
    }
}
