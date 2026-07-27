package com.goodnews.backendjava.config;

import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

@Component
public class ReactiveDatabaseSmokeProbe {

    private static final String REQUIRED_SCHEMA_QUERY =
            """
            SELECT
                to_regclass('sources') IS NOT NULL
                AND to_regclass('posts') IS NOT NULL
                AND to_regclass('feedback') IS NOT NULL
                AND to_regclass('post_analysis') IS NOT NULL
                AND to_regclass('preference_profile') IS NOT NULL
                AND to_regclass('settings') IS NOT NULL
                AND to_regclass('secret_settings') IS NOT NULL
                AND to_regclass('read_later') IS NOT NULL
                AND to_regclass('digests') IS NOT NULL
                AND to_regclass('digest_items') IS NOT NULL
                AND EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'digests'
                      AND column_name = 'delivery_slot_key'
                ) AS ready
            """;

    private final DatabaseClient databaseClient;

    public ReactiveDatabaseSmokeProbe(DatabaseClient databaseClient) {
        this.databaseClient = databaseClient;
    }

    public Mono<Boolean> verifyConnectivity() {
        return databaseClient
                .sql("SELECT 1 AS probe")
                .map((row, metadata) -> row.get("probe", Integer.class))
                .one()
                .map(result -> result != null && result == 1);
    }

    public Mono<Boolean> verifyRequiredSchema() {
        return databaseClient
                .sql(REQUIRED_SCHEMA_QUERY)
                .map((row, metadata) -> row.get("ready", Boolean.class))
                .one()
                .map(Boolean.TRUE::equals);
    }
}
