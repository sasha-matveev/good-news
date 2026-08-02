package com.goodnews.backendjava.service;

import com.goodnews.backendjava.api.contract.ApiHttpException;
import com.goodnews.backendjava.api.dto.SourceDtos;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.List;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Service
public class SourceManagementService {
    private final DatabaseClient databaseClient;

    public SourceManagementService(DatabaseClient databaseClient) {
        this.databaseClient = databaseClient;
    }

    public Flux<SourceDtos.SourceResponse> list() {
        return databaseClient
                .sql(
                        """
            SELECT s.*, COUNT(p.id) AS post_count FROM sources s LEFT JOIN posts p ON p.source_id=s.id
            GROUP BY s.id ORDER BY s.id
            """)
                .map((row, metadata) -> source(row))
                .all();
    }

    public Mono<SourceDtos.SourceResponse> create(String rawUrl) {
        String url = normalize(rawUrl);
        return databaseClient
                .sql(
                        """
            INSERT INTO sources (original_url, active, status, created_at, updated_at)
            VALUES (:url, true, 'pending', NOW(), NOW()) RETURNING *, 0::bigint AS post_count
            """)
                .bind("url", url)
                .map((row, metadata) -> source(row))
                .one()
                .onErrorMap(
                        DuplicateKeyException.class,
                        error -> new ApiHttpException(HttpStatus.CONFLICT, "Source already exists for " + url));
    }

    public Mono<SourceDtos.SourceResponse> update(long id, boolean active) {
        return databaseClient
                .sql(
                        """
            UPDATE sources SET active=:active, updated_at=NOW() WHERE id=:id RETURNING *
            """)
                .bind("active", active)
                .bind("id", id)
                .map((row, metadata) -> new SourceRow(
                        row.get("id", Long.class),
                        row.get("display_name", String.class),
                        row.get("original_url", String.class),
                        row.get("feed_url", String.class),
                        row.get("strategy_kind", String.class),
                        Boolean.TRUE.equals(row.get("active", Boolean.class)),
                        row.get("status", String.class),
                        row.get("last_success_at", OffsetDateTime.class),
                        row.get("last_failure_at", OffsetDateTime.class),
                        Boolean.TRUE.equals(row.get("needs_readaptation", Boolean.class)),
                        row.get("readaptation_reason", String.class)))
                .one()
                .flatMap(value -> countPosts(id).map(count -> response(value, count)))
                .switchIfEmpty(Mono.error(notFound()));
    }

    public Mono<SourceDtos.SourceLogResponse> log(long id) {
        return databaseClient
                .sql("SELECT status FROM sources WHERE id=:id")
                .bind("id", id)
                .map((row, metadata) -> row.get("status", String.class))
                .one()
                .map(status -> new SourceDtos.SourceLogResponse(List.of(), !"discovering".equals(status), status))
                .defaultIfEmpty(new SourceDtos.SourceLogResponse(List.of(), true, null));
    }

    @Transactional
    public Mono<Void> delete(long id) {
        Mono<Void> cleanup = databaseClient
                .sql("DELETE FROM digest_items WHERE post_id IN (SELECT id FROM posts WHERE source_id=:id)")
                .bind("id", id)
                .then()
                .then(databaseClient
                        .sql("DELETE FROM post_analysis WHERE post_id IN (SELECT id FROM posts WHERE source_id=:id)")
                        .bind("id", id)
                        .then())
                .then(databaseClient
                        .sql("DELETE FROM read_later WHERE post_id IN (SELECT id FROM posts WHERE source_id=:id)")
                        .bind("id", id)
                        .then())
                .then(databaseClient
                        .sql("DELETE FROM feedback WHERE post_id IN (SELECT id FROM posts WHERE source_id=:id)")
                        .bind("id", id)
                        .then())
                .then(databaseClient
                        .sql("DELETE FROM posts WHERE source_id=:id")
                        .bind("id", id)
                        .then());
        return exists(id)
                .flatMap(exists -> exists
                        ? cleanup.then(databaseClient
                                .sql("DELETE FROM sources WHERE id=:id")
                                .bind("id", id)
                                .then())
                        : Mono.error(notFound()));
    }

    private Mono<Boolean> exists(long id) {
        return databaseClient
                .sql("SELECT EXISTS(SELECT 1 FROM sources WHERE id=:id) AS present")
                .bind("id", id)
                .map((r, m) -> r.get("present", Boolean.class))
                .one();
    }

    private Mono<Integer> countPosts(long id) {
        return databaseClient
                .sql("SELECT COUNT(*) AS cnt FROM posts WHERE source_id=:id")
                .bind("id", id)
                .map((r, m) -> r.get("cnt", Long.class).intValue())
                .one();
    }

    private static ApiHttpException notFound() {
        return new ApiHttpException(HttpStatus.NOT_FOUND, "Source not found");
    }

    static String normalize(String raw) {
        String candidate = raw.trim();
        if (!candidate.contains("://")) {
            candidate = "https://" + candidate;
        }
        int fragment = candidate.indexOf('#');
        if (fragment >= 0) {
            candidate = candidate.substring(0, fragment);
        }
        int query = candidate.indexOf('?');
        if (query >= 0) {
            candidate = candidate.substring(0, query);
        }
        int authorityStart = candidate.indexOf("://") + 3;
        int lastSlash = candidate.lastIndexOf('/');
        if (lastSlash >= authorityStart) {
            int params = candidate.indexOf(';', lastSlash);
            if (params >= 0) {
                candidate = candidate.substring(0, params);
            }
        }
        return candidate.replaceFirst("/+$", "");
    }

    private static SourceDtos.SourceResponse source(io.r2dbc.spi.Row row) {
        return response(
                new SourceRow(
                        row.get("id", Long.class),
                        row.get("display_name", String.class),
                        row.get("original_url", String.class),
                        row.get("feed_url", String.class),
                        row.get("strategy_kind", String.class),
                        Boolean.TRUE.equals(row.get("active", Boolean.class)),
                        row.get("status", String.class),
                        row.get("last_success_at", OffsetDateTime.class),
                        row.get("last_failure_at", OffsetDateTime.class),
                        Boolean.TRUE.equals(row.get("needs_readaptation", Boolean.class)),
                        row.get("readaptation_reason", String.class)),
                row.get("post_count", Long.class).intValue());
    }

    private static SourceDtos.SourceResponse response(SourceRow s, int count) {
        return new SourceDtos.SourceResponse(
                s.id(),
                s.name(),
                s.url(),
                s.feed(),
                s.strategy(),
                s.active(),
                s.status(),
                count,
                format(s.success()),
                format(s.failure()),
                s.readaptation(),
                s.reason());
    }

    private static String format(OffsetDateTime value) {
        return value == null ? null : DateTimeFormatter.ISO_INSTANT.format(value.withOffsetSameInstant(ZoneOffset.UTC));
    }

    private record SourceRow(
            long id,
            String name,
            String url,
            String feed,
            String strategy,
            boolean active,
            String status,
            OffsetDateTime success,
            OffsetDateTime failure,
            boolean readaptation,
            String reason) {}
}
