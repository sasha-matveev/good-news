package com.goodnews.backendjava.api;

import static org.mockito.BDDMockito.given;

import com.goodnews.backendjava.config.ReactiveDatabaseSmokeProbe;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webtestclient.autoconfigure.AutoConfigureWebTestClient;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.reactive.server.WebTestClient;
import reactor.core.publisher.Mono;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@AutoConfigureWebTestClient
@TestPropertySource(properties = "good-news.database.postgres-host=database.example")
class PublicHealthIntegrationTest {

    @Autowired
    private WebTestClient webTestClient;

    @MockitoBean
    private ReactiveDatabaseSmokeProbe database;

    @Test
    void returnsPythonCompatibleSuccessAndOperationalHeaders() {
        given(database.verifyRequiredSchema()).willReturn(Mono.just(true));

        webTestClient
                .get()
                .uri("/api/health")
                .header("X-Correlation-ID", "shadow-smoke-19")
                .exchange()
                .expectStatus()
                .isOk()
                .expectHeader()
                .valueEquals("X-Good-News-Backend", "java")
                .expectHeader()
                .valueEquals("X-Correlation-ID", "shadow-smoke-19")
                .expectBody()
                .json("{\"status\":\"ok\"}");
    }

    @Test
    void returnsServiceUnavailableWhenRequiredSchemaIsMissing() {
        given(database.verifyRequiredSchema()).willReturn(Mono.just(false));

        webTestClient
                .get()
                .uri("/api/health")
                .exchange()
                .expectStatus()
                .isEqualTo(503)
                .expectBody()
                .json("{\"status\":\"error\",\"reason\":\"database or required schema is not ready\"}");
    }

    @Test
    void returnsServiceUnavailableWhenDatabaseCannotBeReached() {
        given(database.verifyRequiredSchema()).willReturn(Mono.error(new IllegalStateException("offline")));

        webTestClient
                .get()
                .uri("/api/health")
                .exchange()
                .expectStatus()
                .isEqualTo(503)
                .expectBody()
                .jsonPath("$.status")
                .isEqualTo("error");
    }
}
