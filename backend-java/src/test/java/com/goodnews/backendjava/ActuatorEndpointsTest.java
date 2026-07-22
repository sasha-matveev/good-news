package com.goodnews.backendjava;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.AutoConfigureWebTestClient;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@AutoConfigureWebTestClient
@TestPropertySource(properties = "spring.flyway.enabled=false")
class ActuatorEndpointsTest {

    @Autowired
    private WebTestClient webTestClient;

    @Test
    void healthEndpointIsPublic() {
        webTestClient
                .get()
                .uri("/actuator/health")
                .exchange()
                .expectStatus()
                .isOk()
                .expectHeader()
                .valueEquals("X-Good-News-Backend", "java")
                .expectBody()
                .jsonPath("$.status")
                .isEqualTo("UP");
    }

    @Test
    void prometheusEndpointIsNotPubliclyExposed() {
        webTestClient
                .get()
                .uri("/actuator/prometheus")
                .exchange()
                .expectStatus()
                .isUnauthorized();
    }

    @Test
    void actuatorIndexStaysProtected() {
        webTestClient.get().uri("/actuator").exchange().expectStatus().isUnauthorized();
    }
}
