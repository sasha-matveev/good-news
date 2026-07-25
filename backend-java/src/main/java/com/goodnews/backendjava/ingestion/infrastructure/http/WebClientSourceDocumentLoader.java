package com.goodnews.backendjava.ingestion.infrastructure.http;

import com.goodnews.backendjava.ingestion.application.SourceIngestionException;
import com.goodnews.backendjava.ingestion.application.port.SourceDocumentLoader;
import io.netty.channel.ChannelOption;
import java.net.URI;
import java.time.Duration;
import java.util.concurrent.TimeoutException;
import java.util.function.UnaryOperator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientRequestException;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.Exceptions;
import reactor.core.publisher.Mono;
import reactor.netty.http.client.HttpClient;
import reactor.util.retry.Retry;

public class WebClientSourceDocumentLoader implements SourceDocumentLoader {
    private static final Logger LOG = LoggerFactory.getLogger(WebClientSourceDocumentLoader.class);
    private final WebClient.Builder clientBuilder;
    private final PublicSourceUrlPolicy urlPolicy;
    private final UnaryOperator<HttpClient> clientCustomizer;

    public WebClientSourceDocumentLoader(WebClient.Builder clientBuilder, PublicSourceUrlPolicy urlPolicy) {
        this(clientBuilder, urlPolicy, UnaryOperator.identity());
    }

    WebClientSourceDocumentLoader(
            WebClient.Builder clientBuilder,
            PublicSourceUrlPolicy urlPolicy,
            UnaryOperator<HttpClient> clientCustomizer) {
        this.clientBuilder = clientBuilder;
        this.urlPolicy = urlPolicy;
        this.clientCustomizer = clientCustomizer;
    }

    @Override
    public Mono<String> load(String url) {
        return urlPolicy.validate(url).flatMap(this::loadValidated);
    }

    @Override
    public Mono<Void> validate(String url) {
        return urlPolicy.validate(url).then();
    }

    private Mono<String> loadValidated(PublicSourceUrlPolicy.ValidatedUrl validated) {
        URI uri = validated.uri();
        PinnedAddressResolverGroup resolver = new PinnedAddressResolverGroup(validated.addresses());
        HttpClient httpClient = clientCustomizer.apply(HttpClient.newConnection()
                .followRedirect(false)
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 5_000)
                .responseTimeout(Duration.ofSeconds(15))
                .resolver(resolver));
        WebClient client = clientBuilder
                .clone()
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                .defaultHeader("User-Agent", "GoodNews/1.0 source-ingestion")
                .build();
        return client.get()
                .uri(uri)
                .retrieve()
                .onStatus(
                        status -> status.isError() || status.is3xxRedirection(), response -> response.createException())
                .bodyToMono(String.class)
                .filter(body -> !body.isBlank())
                .switchIfEmpty(Mono.error(new SourceIngestionException("Source document is empty")))
                .timeout(Duration.ofSeconds(20))
                .retryWhen(Retry.backoff(2, Duration.ofMillis(100))
                        .maxBackoff(Duration.ofSeconds(1))
                        .filter(WebClientSourceDocumentLoader::transientFailure)
                        .doBeforeRetry(signal -> LOG.warn(
                                "Transient source fetch failure for host {}; retry {}",
                                uri.getHost(),
                                signal.totalRetries() + 1)))
                .onErrorMap(
                        error -> !(error instanceof SourceIngestionException),
                        error -> new SourceIngestionException(
                                "Unable to fetch source document from " + uri.getHost(), error))
                .doFinally(signal -> resolver.close());
    }

    static boolean transientFailure(Throwable error) {
        Throwable failure = Exceptions.unwrap(error);
        if (failure instanceof WebClientResponseException response) {
            return response.getStatusCode().value() == 429
                    || response.getStatusCode().is5xxServerError();
        }
        return failure instanceof WebClientRequestException || failure instanceof TimeoutException;
    }
}
