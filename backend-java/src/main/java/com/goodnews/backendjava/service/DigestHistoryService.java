package com.goodnews.backendjava.service;

import com.goodnews.backendjava.api.contract.ApiHttpException;
import com.goodnews.backendjava.api.dto.DigestDtos;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Service
public class DigestHistoryService {
    private final DatabaseClient databaseClient;

    public DigestHistoryService(DatabaseClient databaseClient) {
        this.databaseClient = databaseClient;
    }

    public Flux<DigestDtos.DigestListItemResponse> listSentDigests() {
        return databaseClient.sql("""
                SELECT d.id, d.digest_type, d.status, d.sent_at, COUNT(di.id) AS included_post_count
                FROM digests d LEFT JOIN digest_items di ON di.digest_id = d.id
                WHERE d.digest_type IN ('daily', 'weekly') AND d.status = 'sent' AND d.sent_at IS NOT NULL
                GROUP BY d.id ORDER BY d.sent_at DESC, d.id DESC
                """)
            .map((row, metadata) -> new DigestDtos.DigestListItemResponse(
                row.get("id", Long.class), row.get("digest_type", String.class), row.get("status", String.class),
                format(row.get("sent_at", OffsetDateTime.class)), row.get("included_post_count", Long.class).intValue()))
            .all();
    }

    public Mono<DigestDtos.DigestDetailResponse> getSentDigest(long digestId) {
        Mono<DigestRow> digest = databaseClient.sql("""
                SELECT id, digest_type, status, sent_at, subject, html_body FROM digests
                WHERE id = :id AND digest_type IN ('daily', 'weekly') AND status = 'sent' AND sent_at IS NOT NULL
                """).bind("id", digestId)
            .map((row, metadata) -> new DigestRow(row.get("id", Long.class), row.get("digest_type", String.class),
                row.get("status", String.class), row.get("sent_at", OffsetDateTime.class),
                row.get("subject", String.class), row.get("html_body", String.class))).one();
        return digest.flatMap(value -> includedPosts(digestId).collectList().map(posts ->
            new DigestDtos.DigestDetailResponse(value.id(), value.type(), value.status(), format(value.sentAt()),
                value.subject(), posts, value.htmlBody())))
            .switchIfEmpty(Mono.error(new ApiHttpException(HttpStatus.NOT_FOUND, "Digest not found")));
    }

    private Flux<DigestDtos.DigestIncludedPostResponse> includedPosts(long digestId) {
        return databaseClient.sql("""
                SELECT p.id, p.title, f.state AS feedback_state FROM digest_items di
                JOIN posts p ON p.id = di.post_id LEFT JOIN feedback f ON f.post_id = p.id
                WHERE di.digest_id = :id ORDER BY di.rank_position ASC, di.id ASC
                """).bind("id", digestId)
            .map((row, metadata) -> new DigestDtos.DigestIncludedPostResponse(row.get("id", Long.class),
                row.get("title", String.class), row.get("feedback_state", String.class))).all();
    }

    private static String format(OffsetDateTime value) {
        return value == null ? null : DateTimeFormatter.ISO_INSTANT.format(value.withOffsetSameInstant(ZoneOffset.UTC));
    }

    private record DigestRow(long id, String type, String status, OffsetDateTime sentAt, String subject, String htmlBody) {}
}
