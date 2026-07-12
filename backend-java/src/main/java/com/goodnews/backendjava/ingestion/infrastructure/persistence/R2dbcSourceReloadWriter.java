package com.goodnews.backendjava.ingestion.infrastructure.persistence;

import com.goodnews.backendjava.ingestion.application.port.SourceReloadWriter;
import com.goodnews.backendjava.ingestion.model.CandidatePost;
import com.goodnews.backendjava.ingestion.model.SourceDefinition;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.HexFormat;
import java.util.List;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Component;
import org.springframework.transaction.reactive.TransactionalOperator;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Component
public final class R2dbcSourceReloadWriter implements SourceReloadWriter {
    private final DatabaseClient database;
    private final TransactionalOperator transactions;
    private final IngestMetadataSerializer metadata;

    public R2dbcSourceReloadWriter(
            DatabaseClient database, TransactionalOperator transactions, IngestMetadataSerializer metadata) {
        this.database = database;
        this.transactions = transactions;
        this.metadata = metadata;
    }

    @Override
    public Mono<ReloadWriteResult> replaceRecentPosts(
            SourceDefinition source, List<CandidatePost> candidates, Instant cutoff, Instant synchronizedAt) {
        return transactions.transactional(
                deleteRecent(source.id(), cutoff).flatMap(deleted -> Flux.fromIterable(candidates)
                        .concatMap(candidate -> insert(source, candidate, synchronizedAt))
                        .reduce(0, Integer::sum)
                        .flatMap(reloaded -> markSuccess(source.id(), synchronizedAt)
                                .thenReturn(new ReloadWriteResult(deleted, reloaded)))));
    }

    private Mono<Integer> deleteRecent(long sourceId, Instant cutoff) {
        String matching =
                "SELECT id FROM posts WHERE source_id=:sourceId AND COALESCE(published_at, created_at)>=:cutoff";
        return database.sql("DELETE FROM digest_items WHERE post_id IN (" + matching + ")")
                .bind("sourceId", sourceId)
                .bind("cutoff", OffsetDateTime.ofInstant(cutoff, ZoneOffset.UTC))
                .fetch()
                .rowsUpdated()
                .then(database.sql("DELETE FROM feedback WHERE post_id IN (" + matching + ")")
                        .bind("sourceId", sourceId)
                        .bind("cutoff", OffsetDateTime.ofInstant(cutoff, ZoneOffset.UTC))
                        .then())
                .then(database.sql("DELETE FROM read_later WHERE post_id IN (" + matching + ")")
                        .bind("sourceId", sourceId)
                        .bind("cutoff", OffsetDateTime.ofInstant(cutoff, ZoneOffset.UTC))
                        .then())
                .then(database.sql("DELETE FROM post_analysis WHERE post_id IN (" + matching + ")")
                        .bind("sourceId", sourceId)
                        .bind("cutoff", OffsetDateTime.ofInstant(cutoff, ZoneOffset.UTC))
                        .then())
                .then(database.sql(
                                "DELETE FROM posts WHERE source_id=:sourceId AND COALESCE(published_at, created_at)>=:cutoff")
                        .bind("sourceId", sourceId)
                        .bind("cutoff", OffsetDateTime.ofInstant(cutoff, ZoneOffset.UTC))
                        .fetch()
                        .rowsUpdated())
                .map(Long::intValue);
    }

    private Mono<Integer> insert(SourceDefinition source, CandidatePost post, Instant at) {
        DatabaseClient.GenericExecuteSpec query = database.sql(
                        """
                INSERT INTO posts (source_id, canonical_url, title, published_at, raw_content, content_hash, ingest_metadata, created_at, updated_at)
                VALUES (:sourceId, :url, :title, :publishedAt, :content, :hash, :metadata, NOW(), NOW()) ON CONFLICT DO NOTHING
                """)
                .bind("sourceId", source.id())
                .bind("url", post.canonicalUrl())
                .bind("title", post.title())
                .bind("content", post.rawContent())
                .bind("hash", hash(post.rawContent().trim()))
                .bind("metadata", metadata.serialize(source, post, at));
        query = post.publishedAt() == null
                ? query.bindNull("publishedAt", OffsetDateTime.class)
                : query.bind("publishedAt", OffsetDateTime.ofInstant(post.publishedAt(), ZoneOffset.UTC));
        return query.fetch().rowsUpdated().map(Long::intValue);
    }

    private Mono<Void> markSuccess(long sourceId, Instant at) {
        return database.sql(
                        "UPDATE sources SET last_success_at=:time, status='ready', needs_readaptation=false, readaptation_reason=NULL, consecutive_failures=0, updated_at=NOW() WHERE id=:id")
                .bind("time", OffsetDateTime.ofInstant(at, ZoneOffset.UTC))
                .bind("id", sourceId)
                .then();
    }

    private static String hash(String value) {
        try {
            return HexFormat.of()
                    .formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (java.security.NoSuchAlgorithmException exception) {
            throw new IllegalStateException(exception);
        }
    }
}
