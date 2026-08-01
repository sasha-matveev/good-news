package com.goodnews.backendjava.security;

import java.util.Set;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.security.web.server.util.matcher.ServerWebExchangeMatcher;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

public final class CookieCsrfProtectionMatcher implements ServerWebExchangeMatcher {

    private static final Set<HttpMethod> SAFE_METHODS =
            Set.of(HttpMethod.GET, HttpMethod.HEAD, HttpMethod.OPTIONS, HttpMethod.TRACE);

    @Override
    public Mono<MatchResult> matches(ServerWebExchange exchange) {
        HttpMethod method = exchange.getRequest().getMethod();
        String authorization = exchange.getRequest().getHeaders().getFirst(HttpHeaders.AUTHORIZATION);
        boolean bearer = authorization != null && authorization.startsWith("Bearer ");
        boolean cookie = !exchange.getRequest().getCookies().isEmpty();
        if (!SAFE_METHODS.contains(method) && cookie && !bearer) {
            return MatchResult.match();
        }
        return MatchResult.notMatch();
    }
}
