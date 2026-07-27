package com.goodnews.backendjava.security;

import com.goodnews.backendjava.api.contract.ApiHttpException;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ServerWebExchange;

final class BearerToken {

    private final ServerWebExchange exchange;

    BearerToken(ServerWebExchange exchange) {
        this.exchange = exchange;
    }

    String value() {
        String header = this.exchange.getRequest().getHeaders().getFirst(HttpHeaders.AUTHORIZATION);
        if (header == null || !header.startsWith("Bearer ")) {
            throw new ApiHttpException(HttpStatus.UNAUTHORIZED, "Missing bearer token.");
        }
        String token = header.substring("Bearer ".length()).trim();
        if (token.isEmpty()) {
            throw new ApiHttpException(HttpStatus.UNAUTHORIZED, "Missing bearer token.");
        }
        return token;
    }
}
