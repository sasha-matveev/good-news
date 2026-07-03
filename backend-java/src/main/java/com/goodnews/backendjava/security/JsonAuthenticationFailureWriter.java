package com.goodnews.backendjava.security;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

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
        } catch (JsonProcessingException exception) {
            return ("{\"detail\":\"" + detail + "\"}").getBytes(StandardCharsets.UTF_8);
        }
    }
}
