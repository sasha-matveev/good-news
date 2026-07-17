package com.goodnews.backendjava.digest;

import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Repository;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Repository
public class DigestRepository {
    private final DatabaseClient database;

    public DigestRepository(DatabaseClient database) {
        this.database = database;
    }

    public Mono<Long> createGenerated(DigestType type, Instant scheduledFor, String subject, String metadataJson) {
        return database.sql(
                        """
                INSERT INTO digests(
                    digest_type, scheduled_for, delivery_slot_key, status, subject, html_body, metadata_json)
                VALUES (:type, :scheduledFor, :deliverySlotKey, 'generated', :subject, '', :metadataJson)
                ON CONFLICT (delivery_slot_key) WHERE delivery_slot_key IS NOT NULL DO UPDATE
                SET status='generated', recipient_email=NULL, subject=EXCLUDED.subject,
                    html_body='', metadata_json=EXCLUDED.metadata_json, sent_at=NULL
                WHERE digests.status='failed'
                RETURNING id
                """)
                .bind("type", type.databaseValue())
                .bind("scheduledFor", atUtc(scheduledFor))
                .bind("deliverySlotKey", deliverySlotKey(type, scheduledFor))
                .bind("subject", subject)
                .bind("metadataJson", metadataJson)
                .map((row, metadata) -> numberToLong(row.get("id")))
                .one()
                .switchIfEmpty(Mono.error(new DigestRunConflictException(type, scheduledFor)));
    }

    public Mono<Void> saveRenderedContent(long digestId, String htmlBody, List<DigestEmailPost> posts) {
        Mono<Void> update = database.sql("UPDATE digests SET html_body=:htmlBody WHERE id=:digestId")
                .bind("htmlBody", htmlBody)
                .bind("digestId", digestId)
                .then();
        Mono<Void> items = database.sql("DELETE FROM digest_items WHERE digest_id=:digestId")
                .bind("digestId", digestId)
                .then()
                .thenMany(Flux.fromIterable(posts).index().concatMap(indexed -> database.sql(
                                """
                        INSERT INTO digest_items(digest_id, post_id, rank_position)
                        VALUES (:digestId, :postId, :rankPosition)
                        """)
                        .bind("digestId", digestId)
                        .bind("postId", indexed.getT2().postId())
                        .bind("rankPosition", Math.toIntExact(indexed.getT1() + 1))
                        .then()))
                .then();
        return update.then(items);
    }

    public Mono<Void> markSkipped(long digestId) {
        return updateStatus(digestId, "skipped");
    }

    public Mono<Void> markFailed(long digestId) {
        return updateStatus(digestId, "failed");
    }

    public Mono<Void> markIndeterminate(long digestId) {
        return updateStatus(digestId, "indeterminate");
    }

    public Mono<String> findRunStatus(DigestType type, Instant scheduledFor) {
        return database.sql(
                        """
                SELECT status FROM digests
                WHERE digest_type=:type AND scheduled_for=:scheduledFor
                ORDER BY CASE WHEN status='failed' THEN 1 ELSE 0 END, id DESC
                LIMIT 1
                """)
                .bind("type", type.databaseValue())
                .bind("scheduledFor", atUtc(scheduledFor))
                .map((row, metadata) -> row.get("status", String.class))
                .one();
    }

    public Mono<Void> markSent(long digestId, String recipient, Instant sentAt) {
        return database.sql(
                        """
                UPDATE digests
                SET status='sent', recipient_email=:recipient, sent_at=:sentAt
                WHERE id=:digestId
                """)
                .bind("recipient", recipient)
                .bind("sentAt", atUtc(sentAt))
                .bind("digestId", digestId)
                .then();
    }

    private Mono<Void> updateStatus(long digestId, String status) {
        return database.sql("UPDATE digests SET status=:status WHERE id=:digestId")
                .bind("status", status)
                .bind("digestId", digestId)
                .then();
    }

    private OffsetDateTime atUtc(Instant value) {
        return OffsetDateTime.ofInstant(value, ZoneOffset.UTC);
    }

    private long numberToLong(Object value) {
        return value instanceof Number number ? number.longValue() : Long.parseLong(String.valueOf(value));
    }

    private String deliverySlotKey(DigestType type, Instant scheduledFor) {
        return type.databaseValue() + ":" + scheduledFor;
    }

    static final class DigestRunConflictException extends RuntimeException {
        private DigestRunConflictException(DigestType type, Instant scheduledFor) {
            super("Digest run slot is already claimed for " + type.databaseValue() + " at " + scheduledFor);
        }
    }
}
