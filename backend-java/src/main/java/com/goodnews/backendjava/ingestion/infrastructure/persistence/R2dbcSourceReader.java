package com.goodnews.backendjava.ingestion.infrastructure.persistence;

import com.goodnews.backendjava.ingestion.application.port.SourceReader;
import com.goodnews.backendjava.ingestion.model.SourceDefinition;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Component
public final class R2dbcSourceReader implements SourceReader {
    private final DatabaseClient databaseClient;
    private final SourceRowMapper rows;

    public R2dbcSourceReader(DatabaseClient databaseClient, SourceRowMapper rows) {
        this.databaseClient = databaseClient;
        this.rows = rows;
    }

    @Override
    public Mono<SourceDefinition> find(long sourceId) {
        return databaseClient
                .sql(
                        """
                SELECT id, original_url, feed_url, strategy_kind, strategy_config, last_success_at
                FROM sources WHERE id=:id
                """)
                .bind("id", sourceId)
                .map((row, metadata) -> rows.map(row))
                .one();
    }

    @Override
    public Flux<Long> findActiveIdsOrdered() {
        return databaseClient
                .sql("SELECT id FROM sources WHERE active=true ORDER BY id")
                .map((row, metadata) -> row.get("id", Long.class))
                .all();
    }
}
