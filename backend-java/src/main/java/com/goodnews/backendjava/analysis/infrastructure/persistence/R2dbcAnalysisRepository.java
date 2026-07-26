package com.goodnews.backendjava.analysis.infrastructure.persistence;

import com.goodnews.backendjava.analysis.application.port.AnalysisRepository;
import com.goodnews.backendjava.analysis.model.AnalysisRequest;
import com.goodnews.backendjava.analysis.model.AnalysisResult;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Component;
import org.springframework.transaction.reactive.TransactionalOperator;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

@Component
public final class R2dbcAnalysisRepository implements AnalysisRepository {
    private final DatabaseClient database;
    private final TransactionalOperator transactions;
    private final ObjectMapper objectMapper;

    public R2dbcAnalysisRepository(
            DatabaseClient database, TransactionalOperator transactions, ObjectMapper objectMapper) {
        this.database = database;
        this.transactions = transactions;
        this.objectMapper = objectMapper;
    }

    @Override
    public Flux<AnalysisRequest> findPending(int limit) {
        return database.sql(
                        """
                SELECT p.id, p.title, p.raw_content FROM posts p
                LEFT JOIN post_analysis pa ON pa.post_id=p.id
                WHERE pa.id IS NULL ORDER BY p.id LIMIT :limit
                """)
                .bind("limit", limit)
                .map((row, metadata) -> new AnalysisRequest(
                        row.get("id", Integer.class).longValue(),
                        row.get("title", String.class),
                        row.get("raw_content", String.class)))
                .all();
    }

    @Override
    public Mono<Void> saveResults(List<AnalysisResult> results) {
        if (results.isEmpty()) {
            return Mono.empty();
        }
        Mono<Void> writes = Flux.fromIterable(results).concatMap(this::upsert).then();
        return transactions.transactional(writes);
    }

    @Override
    public Mono<Integer> countPending() {
        return database.sql(
                        """
                SELECT COUNT(*) AS pending FROM posts p
                LEFT JOIN post_analysis pa ON pa.post_id=p.id WHERE pa.id IS NULL
                """)
                .map((row, metadata) -> row.get("pending", Long.class).intValue())
                .one();
    }

    private Mono<Void> upsert(AnalysisResult result) {
        return database.sql(
                        """
                INSERT INTO post_analysis(post_id, summary_ru, metadata_json, created_at, updated_at)
                VALUES (:postId, :summary, :metadata, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(post_id) DO UPDATE SET summary_ru=EXCLUDED.summary_ru,
                    metadata_json=EXCLUDED.metadata_json, updated_at=CURRENT_TIMESTAMP
                """)
                .bind("postId", result.postId())
                .bind("summary", result.summaryRu())
                .bind("metadata", metadata(result))
                .then();
    }

    String metadata(AnalysisResult result) {
        Map<String, Object> metadata = new LinkedHashMap<>();
        metadata.put("topics", result.topics());
        metadata.put("format", result.format());
        metadata.put("technical_depth", result.technicalDepth());
        metadata.put("verdict", result.verdict());
        metadata.put("verdict_reason", result.verdictReason());
        metadata.put("relevance_score", result.relevanceScore());
        try {
            return objectMapper.writeValueAsString(metadata);
        } catch (JacksonException exception) {
            throw new IllegalArgumentException("Analysis result is not serializable", exception);
        }
    }
}
