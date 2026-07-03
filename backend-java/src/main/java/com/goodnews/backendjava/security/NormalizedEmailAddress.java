package com.goodnews.backendjava.security;

import java.util.Locale;

record NormalizedEmailAddress(String value) {

    NormalizedEmailAddress(String value) {
        this.value = value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }
}
