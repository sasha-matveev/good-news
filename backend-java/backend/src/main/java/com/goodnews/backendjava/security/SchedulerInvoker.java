package com.goodnews.backendjava.security;

final class SchedulerInvoker {

    private final NormalizedEmailAddress expected;

    SchedulerInvoker(String email) {
        this.expected = new NormalizedEmailAddress(email);
    }

    boolean matches(TokenClaims claims) {
        return this.expected.value().equals(new NormalizedEmailAddress(claims.email()).value());
    }
}
