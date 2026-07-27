package com.goodnews.backendjava.digest;

import java.net.URI;

final class WebUrlPolicy {
    private WebUrlPolicy() {}

    static boolean isSafeAbsoluteWebUrl(String value) {
        if (value == null || value.isBlank()) {
            return false;
        }
        try {
            URI uri = URI.create(value);
            String scheme = uri.getScheme();
            return uri.isAbsolute()
                    && uri.getHost() != null
                    && ("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme));
        } catch (IllegalArgumentException exception) {
            return false;
        }
    }

    static String requireOrigin(String value, String environmentName) {
        String normalized = stripTrailingSlashes(value == null ? "" : value.strip());
        if (!isSafeAbsoluteWebUrl(normalized)) {
            throw new IllegalStateException("Invalid public origin contract " + environmentName);
        }
        URI uri = URI.create(normalized);
        if (uri.getRawUserInfo() != null
                || uri.getRawQuery() != null
                || uri.getRawFragment() != null
                || (uri.getRawPath() != null && !uri.getRawPath().isEmpty())) {
            throw new IllegalStateException("Invalid public origin contract " + environmentName);
        }
        return normalized;
    }

    private static String stripTrailingSlashes(String value) {
        int end = value.length();
        while (end > 0 && value.charAt(end - 1) == '/') {
            end--;
        }
        return value.substring(0, end);
    }
}
