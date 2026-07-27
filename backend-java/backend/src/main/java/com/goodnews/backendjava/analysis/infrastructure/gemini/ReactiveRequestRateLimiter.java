package com.goodnews.backendjava.analysis.infrastructure.gemini;

import java.time.Duration;
import java.util.concurrent.atomic.AtomicLong;
import reactor.core.publisher.Mono;

public final class ReactiveRequestRateLimiter {
    private final long intervalNanos;
    private final AtomicLong nextReservation = new AtomicLong();

    public ReactiveRequestRateLimiter(int maxRequestsPerMinute) {
        this.intervalNanos = Duration.ofMinutes(1).toNanos() / maxRequestsPerMinute;
    }

    public Mono<Void> acquire() {
        long now = System.nanoTime();
        long reserved;
        long observed;
        do {
            observed = nextReservation.get();
            reserved = Math.max(now, observed);
        } while (!nextReservation.compareAndSet(observed, reserved + intervalNanos));
        return Mono.delay(Duration.ofNanos(Math.max(0, reserved - now))).then();
    }
}
