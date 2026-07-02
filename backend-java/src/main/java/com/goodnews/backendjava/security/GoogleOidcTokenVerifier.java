package com.goodnews.backendjava.security;

import reactor.core.publisher.Mono;

public interface GoogleOidcTokenVerifier {

    Mono<TokenClaims> verify(String token);
}
