package com.goodnews.backendjava.ingestion.infrastructure.persistence;

import com.goodnews.backendjava.ingestion.application.port.SourceSyncWriter;
import com.goodnews.backendjava.ingestion.model.CandidatePost;
import com.goodnews.backendjava.ingestion.model.SourceDefinition;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
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
public final class R2dbcSourceSyncWriter implements SourceSyncWriter {
    private final DatabaseClient databaseClient;
    private final TransactionalOperator transactions;
    private final IngestMetadataSerializer metadata;

    public R2dbcSourceSyncWriter(
            DatabaseClient databaseClient, TransactionalOperator transactions, IngestMetadataSerializer metadata) {
        this.databaseClient = databaseClient;
        this.transactions = transactions;
        this.metadata = metadata;
    }

    @Override
    public Mono<Void> completeSuccessfulSync(
            SourceDefinition source, List<CandidatePost> posts, Instant synchronizedAt) {
        List<PreparedPost> prepared = posts.stream()
                .map(post -> new PreparedPost(
                        post, sha256(post.rawContent().trim()), metadata.serialize(source, post, synchronizedAt)))
                .toList();
        Mono<Void> write = Flux.fromIterable(prepared)
                .concatMap(post -> insert(source.id(), post))
                .then(markSuccess(source.id(), synchronizedAt));
        return transactions.transactional(write);
    }

    @Override
    public Mono<Void> recordFailedSync(long sourceId, Instant failedAt) {
        return transactions.transactional(databaseClient
                .sql(
                        """
                UPDATE sources SET last_failure_at=:time, status='failing',
                consecutive_failures=consecutive_failures+1, updated_at=NOW() WHERE id=:id
                """)
                .bind("time", OffsetDateTime.ofInstant(failedAt, ZoneOffset.UTC))
                .bind("id", sourceId)
                .then());
    }

    private Mono<Void> insert(long sourceId, PreparedPost prepared) {
        CandidatePost post = prepared.post();
        DatabaseClient.GenericExecuteSpec query = databaseClient
                .sql(
                        """
                INSERT INTO posts (source_id, canonical_url, title, published_at, raw_content,
                    content_hash, ingest_metadata, created_at, updated_at)
                VALUES (:sourceId, :url, :title, :publishedAt, :content, :hash, :metadata, NOW(), NOW())
                ON CONFLICT DO NOTHING
                """)
                .bind("sourceId", sourceId)
                .bind("url", post.canonicalUrl())
                .bind("title", post.title())
                .bind("content", post.rawContent())
                .bind("hash", prepared.contentHash())
                .bind("metadata", prepared.metadata());
        query = post.publishedAt() == null
                ? query.bindNull("publishedAt", OffsetDateTime.class)
                : query.bind("publishedAt", OffsetDateTime.ofInstant(post.publishedAt(), ZoneOffset.UTC));
        return query.then();
    }

    private Mono<Void> markSuccess(long sourceId, Instant synchronizedAt) {
        return databaseClient
                .sql(
                        """
                UPDATE sources SET last_success_at=:time, status='ready', needs_readaptation=false,
                readaptation_reason=NULL, consecutive_failures=0, updated_at=NOW() WHERE id=:id
                """)
                .bind("time", OffsetDateTime.ofInstant(synchronizedAt, ZoneOffset.UTC))
                .bind("id", sourceId)
                .then();
    }

    private static String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    private record PreparedPost(CandidatePost post, String contentHash, String metadata) {}
}
