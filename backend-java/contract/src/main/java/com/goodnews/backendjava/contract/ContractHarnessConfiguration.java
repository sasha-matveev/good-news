package com.goodnews.backendjava.contract;

import com.goodnews.backendjava.ingestion.application.port.SourceDocumentLoader;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.core.env.Environment;
import tools.jackson.databind.ObjectMapper;

@Configuration
public class ContractHarnessConfiguration {

    @Bean
    @Primary
    Clock contractClock(Environment environment) {
        return Clock.fixed(Instant.parse(environment.getRequiredProperty("GOOD_NEWS_FIXED_NOW")), ZoneOffset.UTC);
    }

    @Bean
    @Primary
    ContractTokenVerifier contractTokenVerifier(Environment environment, ObjectMapper objectMapper) {
        return new ContractTokenVerifier(
                environment.getRequiredProperty("GOOD_NEWS_CONTRACT_AUTH_TOKENS_JSON"), objectMapper);
    }

    @Bean
    @Primary
    SourceDocumentLoader contractSourceDocumentLoader(Environment environment, ObjectMapper objectMapper) {
        return new ContractSourceDocumentLoader(
                environment.getRequiredProperty("GOOD_NEWS_INGESTION_RESPONSES_JSON"), objectMapper);
    }
}
