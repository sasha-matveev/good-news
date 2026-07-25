package com.goodnews.backendjava.api;

import com.goodnews.backendjava.api.contract.ApiErrorHandler;
import com.goodnews.backendjava.api.contract.ApiHttpException;
import com.goodnews.backendjava.api.dto.FeedbackDtos;
import com.goodnews.backendjava.api.dto.SettingsDtos;
import com.goodnews.backendjava.ingestion.application.SourceNotFoundException;
import jakarta.validation.Valid;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.AutoConfigureWebTestClient;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.config.web.server.ServerHttpSecurity;
import org.springframework.security.web.server.SecurityWebFilterChain;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        classes = {
            com.goodnews.backendjava.BackendJavaApplication.class,
            ExceptionHandlerContractTest.ContractController.class,
            ExceptionHandlerContractTest.TestSecurityConfiguration.class,
            ApiErrorHandler.class
        })
@AutoConfigureWebTestClient
@TestPropertySource(properties = "spring.flyway.enabled=false")
class ExceptionHandlerContractTest {

    @Autowired
    private WebTestClient webTestClient;

    @Test
    void validationErrorsUseFastApiCompatible422Shape() {
        webTestClient
                .put()
                .uri("/contract/settings")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(
                        """
                {
                  "daily_digest_time": "25:99",
                  "weekly_digest_day_of_week": "funday",
                  "weekly_digest_time": "12:00",
                  "smtp_port": 587,
                  "smtp_security_mode": "starttls",
                  "daily_digest_enabled": true,
                  "daily_digest_catch_up_enabled": true,
                  "weekly_digest_enabled": false,
                  "weekly_digest_catch_up_enabled": true,
                  "analysis_summary_prompt": "",
                  "analysis_verdict_reason_prompt": ""
                }
                """)
                .exchange()
                .expectStatus()
                .isEqualTo(HttpStatus.UNPROCESSABLE_ENTITY)
                .expectBody()
                .jsonPath(
                        "$.detail[?(@.loc[0]=='body' && @.loc[1]=='daily_digest_time' && @.msg=='daily_digest_time must use HH:MM format')]")
                .exists();
    }

    @Test
    void missingRequiredFieldsStillUse422EnvelopeForTrulyRequiredFields() {
        webTestClient
                .put()
                .uri("/contract/settings")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(
                        """
                {
                  "daily_digest_time": "12:00",
                  "weekly_digest_day_of_week": "fri",
                  "weekly_digest_time": "16:30",
                  "smtp_security_mode": "starttls",
                  "analysis_summary_prompt": "",
                  "analysis_verdict_reason_prompt": ""
                }
                """)
                .exchange()
                .expectStatus()
                .isEqualTo(HttpStatus.UNPROCESSABLE_ENTITY)
                .expectBody()
                .jsonPath("$.detail[?(@.loc[1]=='smtp_port')]")
                .exists();
    }

    @Test
    void omittedDigestBooleansDefaultInsteadOfReturning422() {
        webTestClient
                .put()
                .uri("/contract/settings")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(
                        """
                {
                  "daily_digest_time": "12:00",
                  "weekly_digest_day_of_week": "fri",
                  "weekly_digest_time": "16:30",
                  "smtp_port": 587,
                  "smtp_security_mode": "starttls",
                  "analysis_summary_prompt": "",
                  "analysis_verdict_reason_prompt": ""
                }
                """)
                .exchange()
                .expectStatus()
                .isOk()
                .expectBody()
                .jsonPath("$.daily_digest_enabled")
                .isEqualTo(true)
                .jsonPath("$.daily_digest_catch_up_enabled")
                .isEqualTo(true)
                .jsonPath("$.weekly_digest_enabled")
                .isEqualTo(false)
                .jsonPath("$.weekly_digest_catch_up_enabled")
                .isEqualTo(true);
    }

    @Test
    void feedbackStateValidationOwnsItsFastApiCompatibleLiteralError() {
        webTestClient
                .post()
                .uri("/contract/feedback")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{\"state\":\"unknown\"}")
                .exchange()
                .expectStatus()
                .isEqualTo(HttpStatus.UNPROCESSABLE_ENTITY)
                .expectBody()
                .jsonPath("$.detail[0].loc[0]")
                .isEqualTo("body")
                .jsonPath("$.detail[0].loc[1]")
                .isEqualTo("state")
                .jsonPath("$.detail[0].msg")
                .isEqualTo("Input should be 'interesting', 'not_interesting', 'want_to_read' or 'norm'")
                .jsonPath("$.detail[0].type")
                .isEqualTo("literal_error")
                .jsonPath("$.detail[0].input")
                .isEqualTo("unknown")
                .jsonPath("$.detail[0].ctx.expected")
                .isEqualTo("'interesting', 'not_interesting', 'want_to_read' or 'norm'");
    }

    @Test
    void httpExceptionsExposeLegacyDetailEnvelope() {
        webTestClient
                .post()
                .uri("/contract/not-found")
                .exchange()
                .expectStatus()
                .isNotFound()
                .expectBody()
                .jsonPath("$.detail")
                .isEqualTo("Post not found");
    }

    @Test
    void missingSourceApplicationFailureMapsTo404() {
        webTestClient
                .post()
                .uri("/contract/source-not-found")
                .exchange()
                .expectStatus()
                .isNotFound()
                .expectBody()
                .jsonPath("$.detail")
                .isEqualTo("Source not found");
    }

    @RestController
    static class ContractController {

        @PutMapping("/contract/settings")
        SettingsDtos.SettingsUpdateRequest validateSettings(
                @Valid @RequestBody SettingsDtos.SettingsUpdateRequest request) {
            return request;
        }

        @PostMapping("/contract/not-found")
        void notFound() {
            throw new ApiHttpException(HttpStatus.NOT_FOUND, "Post not found");
        }

        @PostMapping("/contract/feedback")
        void validateFeedback(@Valid @RequestBody FeedbackDtos.FeedbackUpdateRequest request) {}

        @PostMapping("/contract/source-not-found")
        void sourceNotFound() {
            throw new SourceNotFoundException(17L);
        }
    }

    @TestConfiguration
    static class TestSecurityConfiguration {

        @Bean
        SecurityWebFilterChain testSecurityWebFilterChain(ServerHttpSecurity http) {
            return http.csrf(ServerHttpSecurity.CsrfSpec::disable)
                    .authorizeExchange(exchanges -> exchanges.anyExchange().permitAll())
                    .httpBasic(ServerHttpSecurity.HttpBasicSpec::disable)
                    .formLogin(ServerHttpSecurity.FormLoginSpec::disable)
                    .build();
        }
    }
}
