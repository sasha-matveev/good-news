package com.goodnews.backendjava.security;

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
import tools.jackson.databind.ObjectMapper;

@Component
public class UserAuthenticationWebFilter implements WebFilter {

    private final GoodNewsProperties properties;
    private final FirebaseTokenVerifier tokenVerifier;
    private final JsonAuthenticationFailureWriter failures;

    public UserAuthenticationWebFilter(
            GoodNewsProperties properties, FirebaseTokenVerifier tokenVerifier, ObjectMapper objectMapper) {
        this.properties = properties;
        this.tokenVerifier = tokenVerifier;
        this.failures = new JsonAuthenticationFailureWriter(objectMapper);
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        if (!requiresAuthentication(exchange)) {
            return chain.filter(exchange);
        }
        if (isBlank(properties.auth().firebaseProjectId())) {
            return chain.filter(exchange);
        }
        String token;
        try {
            token = new BearerToken(exchange).value();
        } catch (ApiHttpException exception) {
            return this.failures.write(exchange, exception.getStatus(), exception.getMessage());
        }
        AllowedEmails allowedEmails = new AllowedEmails(this.properties.auth().allowedEmails());
        return tokenVerifier
                .verify(token)
                .onErrorResume(exception -> this.failures
                        .write(exchange, HttpStatus.UNAUTHORIZED, "Invalid token.")
                        .then(Mono.empty()))
                .flatMap(claims -> {
                    String email = new NormalizedEmailAddress(claims.email()).value();
                    if (!claims.emailVerified() || !allowedEmails.contains(claims)) {
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
        if (HttpMethod.OPTIONS.equals(exchange.getRequest().getMethod())) {
            return false;
        }
        String path = exchange.getRequest().getPath().value();
        return path.startsWith("/api/") && !path.equals("/api/health");
    }

    private boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}
