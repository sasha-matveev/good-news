package com.goodnews.backendjava.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.goodnews.backendjava.api.contract.ApiHttpException;
import com.goodnews.backendjava.config.GoodNewsProperties;
import org.springframework.http.HttpMethod;
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
    private final JsonAuthenticationFailureWriter failures;

    public SchedulerAuthenticationWebFilter(
            GoodNewsProperties properties, GoogleOidcTokenVerifier tokenVerifier, ObjectMapper objectMapper) {
        this.properties = properties;
        this.tokenVerifier = tokenVerifier;
        this.failures = new JsonAuthenticationFailureWriter(objectMapper);
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        if (!requiresAuthentication(exchange)) {
            return chain.filter(exchange);
        }
        if (isBlank(properties.scheduler().invoker())) {
            return this.failures.write(
                    exchange, HttpStatus.SERVICE_UNAVAILABLE, "Scheduler invoker is not configured.");
        }
        String token;
        try {
            token = new BearerToken(exchange).value();
        } catch (ApiHttpException exception) {
            return this.failures.write(exchange, exception.getStatus(), exception.getMessage());
        }
        SchedulerInvoker schedulerInvoker =
                new SchedulerInvoker(this.properties.scheduler().invoker());
        return tokenVerifier
                .verify(token)
                .onErrorResume(exception -> this.failures
                        .write(exchange, HttpStatus.UNAUTHORIZED, "Invalid token.")
                        .then(Mono.empty()))
                .flatMap(claims -> {
                    String email = new NormalizedEmailAddress(claims.email()).value();
                    if (!claims.emailVerified() || !schedulerInvoker.matches(claims)) {
                        return this.failures.write(exchange, HttpStatus.FORBIDDEN, "Not allowed.");
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

    private boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}
