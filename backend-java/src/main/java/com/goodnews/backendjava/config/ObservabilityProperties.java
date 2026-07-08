package com.goodnews.backendjava.config;

import org.springframework.boot.context.properties.bind.DefaultValue;

public record ObservabilityProperties(
    String grafanaOrigin,
    @DefaultValue("127.0.0.1") String grafanaHost,
    @DefaultValue("3000") int grafanaHostPort
) {

    public String grafanaBaseUrl() {
        String normalizedOrigin = normalize(grafanaOrigin);
        if (normalizedOrigin != null) {
            return normalizedOrigin;
        }
        return "http://" + grafanaHost + ":" + grafanaHostPort;
    }

    public String dashboardUrl() {
        return grafanaBaseUrl() + "/d/good-news-overview/good-news-observability-overview";
    }

    private String normalize(String value) {
        if (value == null) {
            return null;
        }
        String normalized = value.strip().replaceAll("/+$", "");
        return normalized.isEmpty() ? null : normalized;
    }
}
