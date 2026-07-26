package com.goodnews.backendjava.security;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webtestclient.autoconfigure.AutoConfigureWebTestClient;
import org.springframework.http.HttpStatus;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        classes = {
            com.goodnews.backendjava.BackendJavaApplication.class,
            ReactiveSecurityOpenApiTest.OpenApiController.class
        })
@AutoConfigureWebTestClient
@TestPropertySource(properties = "spring.flyway.enabled=false")
class ReactiveSecurityOpenApiTest {

    @Autowired
    private WebTestClient webTestClient;

    @Test
    void apiStaysOpenWhenFirebaseAuthIsNotConfigured() {
        webTestClient
                .get()
                .uri("/api/test/open")
                .exchange()
                .expectStatus()
                .isEqualTo(HttpStatus.OK)
                .expectBody()
                .jsonPath("$.status")
                .isEqualTo("ok");
    }

    @RestController
    static class OpenApiController {

        @GetMapping("/api/test/open")
        Mono<StatusResponse> open() {
            return Mono.just(new StatusResponse("ok"));
        }
    }

    record StatusResponse(String status) {}
}
