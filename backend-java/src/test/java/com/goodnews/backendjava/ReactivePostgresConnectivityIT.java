package com.goodnews.backendjava;

import static org.assertj.core.api.Assertions.assertThat;

import com.goodnews.backendjava.config.ReactiveDatabaseSmokeProbe;
import io.r2dbc.spi.Connection;
import io.r2dbc.spi.ConnectionFactory;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@Testcontainers(disabledWithoutDocker = true)
class ReactivePostgresConnectivityIT {

    @Container
    static final PostgreSQLContainer<?> POSTGRESQL = new PostgreSQLContainer<>("postgres:16-alpine")
            .withDatabaseName("good_news")
            .withUsername("good_news")
            .withPassword("good-news-secret");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("good-news.database.postgres-host", POSTGRESQL::getHost);
        registry.add("good-news.database.postgres-port", POSTGRESQL::getFirstMappedPort);
        registry.add("good-news.database.postgres-database", POSTGRESQL::getDatabaseName);
        registry.add("good-news.database.postgres-user", POSTGRESQL::getUsername);
        registry.add("good-news.database.postgres-password", POSTGRESQL::getPassword);
        registry.add("good-news.database.pool-initial-size", () -> 0);
        registry.add("good-news.database.pool-max-size", () -> 1);
        registry.add("good-news.database.pool-acquire-timeout", () -> "200ms");
        registry.add("good-news.database.operation-timeout", () -> "200ms");
    }

    @Autowired
    private ReactiveDatabaseSmokeProbe smokeProbe;

    @Autowired
    private ConnectionFactory connectionFactory;

    @Autowired
    private DatabaseClient databaseClient;

    @Test
    void applicationBootsAndConnectsToPostgresReactively() {
        StepVerifier.create(smokeProbe.verifyConnectivity())
                .assertNext(canConnect -> assertThat(canConnect).isTrue())
                .verifyComplete();
    }

    @Test
    void poolRejectsSaturationWithinTheConfiguredAcquireTimeout() {
        Connection heldConnection = Mono.from(connectionFactory.create()).block(Duration.ofSeconds(2));
        assertThat(heldConnection).isNotNull();
        try {
            StepVerifier.create(Mono.from(connectionFactory.create()))
                    .expectErrorSatisfies(error -> assertThat(error.getMessage())
                            .containsIgnoringCase("acquisition")
                            .contains("200ms"))
                    .verify(Duration.ofSeconds(2));
        } finally {
            Mono.from(heldConnection.close()).block(Duration.ofSeconds(2));
        }
    }

    @Test
    void databaseOperationTimeoutCancelsLongRunningStatements() {
        StepVerifier.create(databaseClient
                        .sql("SELECT 1 AS value FROM pg_sleep(1)")
                        .map((row, metadata) -> row.get("value", Integer.class))
                        .one())
                .expectErrorSatisfies(error -> assertThat(error.getMessage()).containsIgnoringCase("statement timeout"))
                .verify(Duration.ofSeconds(2));
    }
}
