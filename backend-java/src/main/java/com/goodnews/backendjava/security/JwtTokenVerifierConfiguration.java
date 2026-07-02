package com.goodnews.backendjava.security;

import com.goodnews.backendjava.config.GoodNewsProperties;
import java.util.List;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.oauth2.core.DelegatingOAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2Error;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2TokenValidatorResult;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtTimestampValidator;
import org.springframework.security.oauth2.jwt.NimbusReactiveJwtDecoder;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

@Configuration
public class JwtTokenVerifierConfiguration {

    private static final String FIREBASE_JWK_SET_URI =
        "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com";
    private static final String GOOGLE_OIDC_JWK_SET_URI = "https://www.googleapis.com/oauth2/v3/certs";

    @Bean
    FirebaseTokenVerifier firebaseTokenVerifier(GoodNewsProperties properties) {
        ReactiveJwtDecoder decoder = buildFirebaseDecoder(properties.auth().firebaseProjectId());
        return token -> decoder.decode(token)
            .map(this::toClaims)
            .subscribeOn(Schedulers.boundedElastic());
    }

    @Bean
    GoogleOidcTokenVerifier googleOidcTokenVerifier(GoodNewsProperties properties) {
        ReactiveJwtDecoder decoder = buildGoogleOidcDecoder(properties.auth().oidcAudience());
        return token -> decoder.decode(token)
            .map(this::toClaims)
            .subscribeOn(Schedulers.boundedElastic());
    }

    private ReactiveJwtDecoder buildFirebaseDecoder(String projectId) {
        NimbusReactiveJwtDecoder decoder = NimbusReactiveJwtDecoder.withJwkSetUri(FIREBASE_JWK_SET_URI).build();
        decoder.setJwtValidator(new DelegatingOAuth2TokenValidator<>(
            new JwtTimestampValidator(),
            audienceValidator(projectId),
            issuerValidator(List.of("https://securetoken.google.com/" + projectId))
        ));
        return decoder;
    }

    private ReactiveJwtDecoder buildGoogleOidcDecoder(String audience) {
        NimbusReactiveJwtDecoder decoder = NimbusReactiveJwtDecoder.withJwkSetUri(GOOGLE_OIDC_JWK_SET_URI).build();
        decoder.setJwtValidator(new DelegatingOAuth2TokenValidator<>(
            new JwtTimestampValidator(),
            audienceValidator(audience),
            issuerValidator(List.of("https://accounts.google.com", "accounts.google.com"))
        ));
        return decoder;
    }

    private OAuth2TokenValidator<Jwt> audienceValidator(String audience) {
        return jwt -> jwt.getAudience().contains(audience)
            ? OAuth2TokenValidatorResult.success()
            : OAuth2TokenValidatorResult.failure(new OAuth2Error("invalid_token", "Token audience did not match.", null));
    }

    private OAuth2TokenValidator<Jwt> issuerValidator(List<String> validIssuers) {
        return jwt -> validIssuers.contains(jwt.getIssuer().toString())
            ? OAuth2TokenValidatorResult.success()
            : OAuth2TokenValidatorResult.failure(new OAuth2Error("invalid_token", "Token issuer did not match.", null));
    }

    private TokenClaims toClaims(Jwt jwt) {
        Object emailVerified = jwt.getClaims().get("email_verified");
        return new TokenClaims(
            jwt.getClaimAsString("email"),
            Boolean.TRUE.equals(emailVerified) || "true".equals(String.valueOf(emailVerified))
        );
    }
}
