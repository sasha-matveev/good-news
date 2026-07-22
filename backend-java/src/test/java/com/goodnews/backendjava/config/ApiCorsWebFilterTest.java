package com.goodnews.backendjava.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;
import org.springframework.mock.web.server.MockServerWebExchange;
import reactor.core.publisher.Mono;

class ApiCorsWebFilterTest {

    @Test
    void acceptsConfiguredFrontendAuthorizationPreflight() {
        GoodNewsProperties properties = mock(GoodNewsProperties.class);
        AppProperties app = mock(AppProperties.class);
        EmailProperties email = mock(EmailProperties.class);
        when(properties.app()).thenReturn(app);
        when(properties.email()).thenReturn(email);
        when(app.frontendPort()).thenReturn(5173);
        when(email.publicFrontendOrigin()).thenReturn("https://good-news.example");
        ApiCorsWebFilter cors = new ApiCorsWebFilter(properties);
        MockServerWebExchange exchange =
                MockServerWebExchange.from(MockServerHttpRequest.options("http://localhost/api/posts")
                        .header(HttpHeaders.ORIGIN, "https://good-news.example")
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, HttpMethod.GET.name())
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_HEADERS, "authorization,x-correlation-id")
                        .build());
        cors.filter(exchange, ignored -> Mono.error(new AssertionError("Preflight reached the application")))
                .block();

        assertThat(exchange.getResponse().getStatusCode()).isNull();
        assertThat(exchange.getResponse().getHeaders().getAccessControlAllowOrigin())
                .isEqualTo("https://good-news.example");
    }
}
