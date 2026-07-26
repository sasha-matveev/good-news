package com.goodnews.backendjava.contract;

import com.goodnews.backendjava.security.FirebaseTokenVerifier;
import com.goodnews.backendjava.security.GoogleOidcTokenVerifier;
import com.goodnews.backendjava.security.TokenClaims;
import reactor.core.publisher.Mono;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

final class ContractTokenVerifier implements FirebaseTokenVerifier, GoogleOidcTokenVerifier {

    private final JsonNode claimsByToken;

    ContractTokenVerifier(String json, ObjectMapper objectMapper) {
        try {
            claimsByToken = objectMapper.readTree(json);
        } catch (Exception exception) {
            throw new IllegalArgumentException("Invalid contract auth fixture", exception);
        }
        if (!claimsByToken.isObject()) {
            throw new IllegalArgumentException("Contract auth fixture must be a JSON object.");
        }
    }

    @Override
    public Mono<TokenClaims> verify(String token) {
        return Mono.fromCallable(() -> {
            JsonNode claims = claimsByToken.get(token);
            if (claims == null || !claims.isObject()) {
                throw new IllegalArgumentException("Unknown contract token.");
            }
            return new TokenClaims(
                    claims.path("email").asString(),
                    claims.path("email_verified").asBoolean(false));
        });
    }
}
