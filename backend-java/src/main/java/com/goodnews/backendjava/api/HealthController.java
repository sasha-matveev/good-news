package com.goodnews.backendjava.api;

import com.goodnews.backendjava.config.ReactiveDatabaseSmokeProbe;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

@RestController
public class HealthController {

    private static final Map<String, String> OK = Map.of("status", "ok");
    private static final Map<String, String> DATABASE_NOT_READY =
            Map.of("status", "error", "reason", "database or required schema is not ready");

    private final ReactiveDatabaseSmokeProbe database;

    public HealthController(ReactiveDatabaseSmokeProbe database) {
        this.database = database;
    }

    @GetMapping("/api/health")
    public Mono<ResponseEntity<Map<String, String>>> health() {
        return database.verifyRequiredSchema()
                .map(ready -> ready
                        ? ResponseEntity.ok(OK)
                        : ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(DATABASE_NOT_READY))
                .onErrorReturn(
                        ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(DATABASE_NOT_READY));
    }
}
