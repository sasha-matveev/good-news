package com.goodnews.backendjava.config;

import com.goodnews.backendjava.security.CookieCsrfProtectionMatcher;
import com.goodnews.backendjava.security.SchedulerAuthenticationWebFilter;
import com.goodnews.backendjava.security.UserAuthenticationWebFilter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.reactive.EnableWebFluxSecurity;
import org.springframework.security.config.web.server.SecurityWebFiltersOrder;
import org.springframework.security.config.web.server.ServerHttpSecurity;
import org.springframework.security.web.server.SecurityWebFilterChain;
import org.springframework.security.web.server.context.NoOpServerSecurityContextRepository;
import org.springframework.security.web.server.savedrequest.NoOpServerRequestCache;

@Configuration
@EnableWebFluxSecurity
public class ActuatorSecurityConfig {

    @Bean
    SecurityWebFilterChain securityWebFilterChain(
            ServerHttpSecurity http,
            UserAuthenticationWebFilter userAuthenticationWebFilter,
            SchedulerAuthenticationWebFilter schedulerAuthenticationWebFilter) {
        return http.authorizeExchange(exchanges -> exchanges
                        .pathMatchers("/actuator/health")
                        .permitAll()
                        .pathMatchers("/api/health")
                        .permitAll()
                        .pathMatchers("/actuator/**")
                        .authenticated()
                        .anyExchange()
                        .permitAll())
                .httpBasic(ServerHttpSecurity.HttpBasicSpec::disable)
                .formLogin(ServerHttpSecurity.FormLoginSpec::disable)
                .securityContextRepository(NoOpServerSecurityContextRepository.getInstance())
                .requestCache(cache -> cache.requestCache(NoOpServerRequestCache.getInstance()))
                .csrf(csrf -> csrf.requireCsrfProtectionMatcher(new CookieCsrfProtectionMatcher()))
                .cors(ServerHttpSecurity.CorsSpec::disable)
                .addFilterAt(schedulerAuthenticationWebFilter, SecurityWebFiltersOrder.AUTHENTICATION)
                .addFilterAfter(userAuthenticationWebFilter, SecurityWebFiltersOrder.AUTHENTICATION)
                .build();
    }
}
