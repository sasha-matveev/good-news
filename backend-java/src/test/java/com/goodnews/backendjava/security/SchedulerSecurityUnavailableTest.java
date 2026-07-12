package com.goodnews.backendjava.security;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.AutoConfigureWebTestClient;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        classes = {
            com.goodnews.backendjava.BackendJavaApplication.class,
            SchedulerSecurityUnavailableTest.InternalJobController.class
        })
@AutoConfigureWebTestClient
@TestPropertySource(properties = "spring.flyway.enabled=false")
class SchedulerSecurityUnavailableTest {

    @Autowired
    private WebTestClient webTestClient;

    @Test
    void internalJobIsUnavailableWithoutInvokerConfiguration() {
        webTestClient
                .post()
                .uri("/internal/jobs/test-unconfigured")
                .exchange()
                .expectStatus()
                .isEqualTo(503)
                .expectBody()
                .jsonPath("$.detail")
                .isEqualTo("Scheduler invoker is not configured.");
    }

    @RestController
    static class InternalJobController {

        @PostMapping("/internal/jobs/test-unconfigured")
        Mono<StatusResponse> run() {
            return Mono.just(new StatusResponse("ok"));
        }
    }

    record StatusResponse(String status) {}
}
