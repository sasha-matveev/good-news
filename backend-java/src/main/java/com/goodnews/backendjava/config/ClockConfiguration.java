package com.goodnews.backendjava.config;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class ClockConfiguration {

    @Bean
    @ConditionalOnMissingBean(Clock.class)
    Clock clock(GoodNewsProperties properties) {
        String fixedNow = properties.app().fixedNow();
        if (fixedNow == null || fixedNow.isBlank()) {
            return Clock.systemUTC();
        }
        return Clock.fixed(Instant.parse(fixedNow), ZoneOffset.UTC);
    }
}
