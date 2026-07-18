package com.goodnews.backendjava.digest;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.goodnews.backendjava.config.GoodNewsProperties;
import java.time.Duration;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.reactive.TransactionalOperator;
import org.springframework.web.util.HtmlUtils;
import reactor.core.publisher.Mono;

@Service
public final class ObservabilityReportGenerator {
    private static final Duration REPORT_WINDOW = Duration.ofHours(24);
    private static final String DASHBOARD_PATH = "/d/good-news-overview/good-news-observability-overview";
    private static final String RENDER_PATH = "/render/d-solo/good-news-overview/good-news-observability-overview";
    private static final String QUERY = "from=now-24h&to=now&viewPanel=1&panelId=1&width=1200&height=630&tz=UTC";

    private final DatabaseClient database;
    private final DigestRepository digests;
    private final GoodNewsProperties properties;
    private final ObjectMapper objectMapper;
    private final TransactionalOperator transactions;

    public ObservabilityReportGenerator(
            DatabaseClient database,
            DigestRepository digests,
            GoodNewsProperties properties,
            ObjectMapper objectMapper,
            TransactionalOperator transactions) {
        this.database = database;
        this.digests = digests;
        this.properties = properties;
        this.objectMapper = objectMapper;
        this.transactions = transactions;
    }

    public Mono<GeneratedDigest> generate(Instant now) {
        return Mono.zip(loadEvents(now), loadFailingSources())
                .flatMap(rows -> {
                    List<TechnicalEvent> events = rows.getT1();
                    List<FailingSource> sources = rows.getT2();
                    String baseUrl = properties.observability().grafanaBaseUrl();
                    String dashboardUrl = baseUrl + DASHBOARD_PATH + "?" + QUERY;
                    String renderUrl = baseUrl + RENDER_PATH + "?" + QUERY;
                    String subject = "Good News observability report for "
                            + now.atZone(ZoneOffset.UTC).toLocalDate();
                    String html = render(subject, now, events, sources, dashboardUrl, renderUrl);
                    return digests.createGenerated(
                                    DigestType.OBSERVABILITY_DAILY,
                                    now,
                                    subject,
                                    metadata(dashboardUrl, renderUrl, events.size(), sources.size()))
                            .flatMap(id -> digests.saveRenderedContent(id, html, List.of())
                                    .thenReturn(new GeneratedDigest(
                                            id,
                                            DigestType.OBSERVABILITY_DAILY,
                                            subject,
                                            html,
                                            List.of(),
                                            0,
                                            events.size())));
                })
                .as(transactions::transactional);
    }

    private Mono<List<TechnicalEvent>> loadEvents(Instant now) {
        return database.sql(
                        """
                SELECT e.severity, e.subsystem, e.event_code, e.summary, e.details, e.created_at,
                       s.display_name AS source_name
                FROM technical_events e
                LEFT JOIN sources s ON s.id = e.source_id
                WHERE e.created_at >= :since
                ORDER BY e.created_at DESC, e.id DESC
                LIMIT 10
                """)
                .bind("since", OffsetDateTime.ofInstant(now.minus(REPORT_WINDOW), ZoneOffset.UTC))
                .map((row, metadata) -> new TechnicalEvent(
                        row.get("severity", String.class),
                        row.get("subsystem", String.class),
                        row.get("event_code", String.class),
                        row.get("summary", String.class),
                        row.get("details", String.class),
                        row.get("source_name", String.class),
                        row.get("created_at", OffsetDateTime.class)))
                .all()
                .collectList();
    }

    private Mono<List<FailingSource>> loadFailingSources() {
        return database.sql(
                        """
                SELECT display_name, original_url, status, consecutive_failures,
                       needs_readaptation, last_failure_at
                FROM sources
                WHERE status <> 'ready' OR consecutive_failures > 0 OR needs_readaptation = TRUE
                ORDER BY needs_readaptation DESC, consecutive_failures DESC, id ASC
                LIMIT 10
                """)
                .map((row, metadata) -> new FailingSource(
                        row.get("display_name", String.class),
                        row.get("original_url", String.class),
                        row.get("status", String.class),
                        number(row.get("consecutive_failures")),
                        Boolean.TRUE.equals(row.get("needs_readaptation", Boolean.class)),
                        row.get("last_failure_at", OffsetDateTime.class)))
                .all()
                .collectList();
    }

    private String metadata(String dashboardUrl, String renderUrl, int eventCount, int failingSourceCount) {
        Map<String, Object> values = new LinkedHashMap<>();
        values.put("dashboard_url", dashboardUrl);
        values.put("render_url", renderUrl);
        values.put("event_count", eventCount);
        values.put("failing_source_count", failingSourceCount);
        try {
            return objectMapper.writeValueAsString(values);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Observability metadata is not serializable", exception);
        }
    }

    private String render(
            String subject,
            Instant now,
            List<TechnicalEvent> events,
            List<FailingSource> sources,
            String dashboardUrl,
            String renderUrl) {
        long warnings = events.stream()
                .filter(event -> "warning".equalsIgnoreCase(event.severity()))
                .count();
        long errors = events.stream()
                .filter(event -> "error".equalsIgnoreCase(event.severity()))
                .count();
        StringBuilder html = new StringBuilder("<html><body>")
                .append("<h1>")
                .append(escape(subject))
                .append("</h1>")
                .append("<p>")
                .append(events.size())
                .append(" technical events in the last 24 hours. ")
                .append(warnings)
                .append(" warning(s), ")
                .append(errors)
                .append(" error(s).</p>")
                .append("<p>")
                .append(sources.size())
                .append(
                        sources.size() == 1
                                ? " source currently needs operator attention.</p>"
                                : " sources currently need operator attention.</p>")
                .append("<p><a href=\"")
                .append(escapeAttribute(dashboardUrl))
                .append("\">Open Grafana dashboard</a></p>")
                .append("<p><a href=\"")
                .append(escapeAttribute(renderUrl))
                .append("\">Open Grafana render URL</a></p>")
                .append("<p><img src=\"")
                .append(escapeAttribute(renderUrl))
                .append("\" alt=\"Grafana observability snapshot for the last 24 hours\" /></p>")
                .append("<h2>Recent technical events</h2><ul>");
        if (events.isEmpty()) {
            html.append("<li>No technical events recorded in the last 24 hours.</li>");
        } else {
            events.forEach(event -> html.append("<li>")
                    .append(format(event.createdAt()))
                    .append(' ')
                    .append(escape(event.severity().toUpperCase()))
                    .append(' ')
                    .append(escape(event.subsystem()))
                    .append(':')
                    .append(escape(event.eventCode()))
                    .append(' ')
                    .append(escape(event.summary()))
                    .append(event.sourceName() == null ? "" : " source=" + escape(event.sourceName()))
                    .append(event.details() == null ? "" : " details=" + escape(event.details()))
                    .append("</li>"));
        }
        html.append("</ul><h2>Current source failures</h2><ul>");
        if (sources.isEmpty()) {
            html.append("<li>No active failing sources.</li>");
        } else {
            sources.forEach(source -> html.append("<li>")
                    .append(escape(source.displayName() == null ? source.originalUrl() : source.displayName()))
                    .append(" status=")
                    .append(escape(source.status()))
                    .append(" failures=")
                    .append(source.consecutiveFailures())
                    .append(" needs_readaptation=")
                    .append(source.needsReadaptation() ? "yes" : "no")
                    .append(" last_failure_at=")
                    .append(format(source.lastFailureAt()))
                    .append("</li>"));
        }
        return html.append("</ul><p>Generated at ")
                .append(format(now))
                .append(".</p></body></html>")
                .toString();
    }

    private int number(Object value) {
        return value instanceof Number number ? number.intValue() : Integer.parseInt(String.valueOf(value));
    }

    private String format(OffsetDateTime value) {
        return value == null ? "n/a" : value.toInstant().toString();
    }

    private String format(Instant value) {
        return value.toString();
    }

    private String escape(String value) {
        return HtmlUtils.htmlEscape(value);
    }

    private String escapeAttribute(String value) {
        return HtmlUtils.htmlEscape(value);
    }

    private record TechnicalEvent(
            String severity,
            String subsystem,
            String eventCode,
            String summary,
            String details,
            String sourceName,
            OffsetDateTime createdAt) {}

    private record FailingSource(
            String displayName,
            String originalUrl,
            String status,
            int consecutiveFailures,
            boolean needsReadaptation,
            OffsetDateTime lastFailureAt) {}
}
