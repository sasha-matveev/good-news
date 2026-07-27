package com.goodnews.backendjava.config;

import java.util.ArrayList;
import java.util.List;
import org.springframework.core.Ordered;
import org.springframework.stereotype.Component;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.reactive.CorsWebFilter;
import org.springframework.web.cors.reactive.UrlBasedCorsConfigurationSource;

@Component
public class ApiCorsWebFilter extends CorsWebFilter implements Ordered {

    public ApiCorsWebFilter(GoodNewsProperties properties) {
        super(configurationSource(properties));
    }

    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE + 1;
    }

    private static UrlBasedCorsConfigurationSource configurationSource(GoodNewsProperties properties) {
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", corsConfiguration(properties));
        return source;
    }

    private static CorsConfiguration corsConfiguration(GoodNewsProperties properties) {
        CorsConfiguration cors = new CorsConfiguration();
        cors.setAllowedOriginPatterns(allowedOrigins(properties));
        cors.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        cors.setAllowedHeaders(List.of("Authorization", "Content-Type", "X-Correlation-ID"));
        cors.setExposedHeaders(List.of("X-Good-News-Backend", "X-Correlation-ID"));
        cors.setAllowCredentials(false);
        cors.setMaxAge(3600L);
        return cors;
    }

    private static List<String> allowedOrigins(GoodNewsProperties properties) {
        List<String> origins = new ArrayList<>();
        origins.add("http://localhost:" + properties.app().frontendPort());
        origins.add("http://127.0.0.1:" + properties.app().frontendPort());
        String frontendOrigin = normalizeOrigin(properties.email().publicFrontendOrigin());
        if (frontendOrigin != null) {
            origins.add(frontendOrigin);
        }
        return List.copyOf(origins);
    }

    private static String normalizeOrigin(String origin) {
        if (origin == null) {
            return null;
        }
        String normalized = origin.strip().replaceAll("/+$", "");
        return normalized.isEmpty() ? null : normalized;
    }
}
