package com.goodnews.backendjava.security;

import reactor.core.publisher.Mono;

public interface FirebaseTokenVerifier {

    Mono<TokenClaims> verify(String token);
}
