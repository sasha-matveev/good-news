package com.goodnews.backendjava.config;

import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

@Component
public class ReactiveDatabaseSmokeProbe {

    private final DatabaseClient databaseClient;

    public ReactiveDatabaseSmokeProbe(DatabaseClient databaseClient) {
        this.databaseClient = databaseClient;
    }

    public Mono<Boolean> verifyConnectivity() {
        return databaseClient.sql("SELECT 1 AS probe")
            .map((row, metadata) -> row.get("probe", Integer.class))
            .one()
            .map(result -> result != null && result == 1);
    }
}
