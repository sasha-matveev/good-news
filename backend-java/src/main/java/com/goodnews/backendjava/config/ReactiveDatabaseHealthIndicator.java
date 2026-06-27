package com.goodnews.backendjava.config;

import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.ReactiveHealthIndicator;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

@Component("postgres")
public class ReactiveDatabaseHealthIndicator implements ReactiveHealthIndicator {

    private final GoodNewsProperties properties;
    private final ReactiveDatabaseSmokeProbe smokeProbe;

    public ReactiveDatabaseHealthIndicator(GoodNewsProperties properties, ReactiveDatabaseSmokeProbe smokeProbe) {
        this.properties = properties;
        this.smokeProbe = smokeProbe;
    }

    @Override
    public Mono<Health> health() {
        if (!properties.database().isExplicitlyConfigured()) {
            return Mono.just(Health.up().withDetail("database", "not-configured").build());
        }

        return smokeProbe.verifyConnectivity()
            .map(connected -> connected
                ? Health.up().withDetail("database", "reachable").build()
                : Health.down().withDetail("database", "unreachable").build())
            .onErrorResume(exception -> Mono.just(
                Health.down(exception).withDetail("database", "unreachable").build()
            ));
    }
}
