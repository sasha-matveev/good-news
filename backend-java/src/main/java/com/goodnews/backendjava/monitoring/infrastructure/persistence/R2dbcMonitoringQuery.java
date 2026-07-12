package com.goodnews.backendjava.monitoring.infrastructure.persistence;

import com.goodnews.backendjava.monitoring.application.MonitoringQueueItem;
import com.goodnews.backendjava.monitoring.application.MonitoringSummary;
import com.goodnews.backendjava.monitoring.application.port.MonitoringQuery;
import java.time.OffsetDateTime;
import java.util.Map;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Component
public final class R2dbcMonitoringQuery implements MonitoringQuery {
    private static final Map<String, String> SERVICES =
            Map.of("content_api", "ok", "analysis_llm", "ok", "source_ingestion", "ok", "delivery", "ok");
    private final DatabaseClient database;

    public R2dbcMonitoringQuery(DatabaseClient database) {
        this.database = database;
    }

    @Override
    public Mono<MonitoringSummary> summary() {
        return database.sql(
                        """
                SELECT (SELECT COUNT(*) FROM sources WHERE active=true) AS sources_active,
                       (SELECT COUNT(*) FROM sources) AS sources_total,
                       (SELECT COUNT(*) FROM posts) AS posts_total,
                       (SELECT COUNT(*) FROM posts p LEFT JOIN post_analysis pa ON pa.post_id=p.id WHERE pa.id IS NULL) AS posts_unranked,
                       (SELECT MAX(last_success_at) FROM sources) AS last_sync_at
                """)
                .map((row, metadata) -> new MonitoringSummary(
                        row.get("sources_active", Long.class).intValue(),
                        row.get("sources_total", Long.class).intValue(),
                        row.get("posts_total", Long.class).intValue(),
                        row.get("posts_unranked", Long.class).intValue(),
                        instant(row.get("last_sync_at", OffsetDateTime.class)),
                        SERVICES))
                .one();
    }

    @Override
    public Flux<MonitoringQueueItem> queue() {
        return database.sql(
                        """
                SELECT p.id AS post_id, p.title, COALESCE(s.display_name, s.original_url) AS source_name, p.created_at
                FROM posts p LEFT JOIN post_analysis pa ON pa.post_id=p.id JOIN sources s ON s.id=p.source_id
                WHERE pa.id IS NULL ORDER BY p.created_at LIMIT 100
                """)
                .map((row, metadata) -> new MonitoringQueueItem(
                        row.get("post_id", Long.class),
                        row.get("title", String.class),
                        row.get("source_name", String.class),
                        instant(row.get("created_at", OffsetDateTime.class))))
                .all();
    }

    private static java.time.Instant instant(OffsetDateTime value) {
        return value == null ? null : value.toInstant();
    }
}
