package com.goodnews.backendjava.security;

import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.Stream;

final class AllowedEmails {

    private final Set<String> values;

    AllowedEmails(String csv) {
        this.values = Stream.of(csv.split(","))
            .map(NormalizedEmailAddress::new)
            .map(NormalizedEmailAddress::value)
            .filter(value -> !value.isEmpty())
            .collect(Collectors.toUnmodifiableSet());
    }

    boolean contains(TokenClaims claims) {
        return this.values.contains(new NormalizedEmailAddress(claims.email()).value());
    }
}
