package com.goodnews.backendjava.security;

import java.nio.charset.StandardCharsets;
import java.util.Map;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

final class JsonAuthenticationFailureWriter {

    private final ObjectMapper objectMapper;

    JsonAuthenticationFailureWriter(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    Mono<Void> write(ServerWebExchange exchange, HttpStatus status, String detail) {
        exchange.getResponse().setStatusCode(status);
        exchange.getResponse().getHeaders().setContentType(MediaType.APPLICATION_JSON);
        DataBuffer buffer = exchange.getResponse().bufferFactory().wrap(this.payload(detail));
        return exchange.getResponse().writeWith(Mono.just(buffer));
    }

    private byte[] payload(String detail) {
        try {
            return this.objectMapper.writeValueAsBytes(Map.of("detail", detail));
        } catch (JacksonException exception) {
            return ("{\"detail\":\"" + detail + "\"}").getBytes(StandardCharsets.UTF_8);
        }
    }
}
