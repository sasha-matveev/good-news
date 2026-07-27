package com.goodnews.backendjava.ingestion.infrastructure.http;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.goodnews.backendjava.ingestion.application.SourceIngestionException;
import io.netty.handler.ssl.SslContextBuilder;
import java.io.IOException;
import java.net.InetAddress;
import java.net.URI;
import java.util.List;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.tls.HandshakeCertificates;
import okhttp3.tls.HeldCertificate;
import org.junit.jupiter.api.Test;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

class WebClientSourceDocumentLoaderTest {
    @Test
    void retriesBoundedNumberOfTimesForTransientResponses() throws IOException {
        try (MockWebServer server = new MockWebServer()) {
            server.enqueue(new MockResponse().setResponseCode(503));
            server.enqueue(new MockResponse().setResponseCode(503));
            server.enqueue(new MockResponse().setResponseCode(200).setBody("feed"));
            WebClientSourceDocumentLoader client = testClient();

            assertThat(client.load(server.url("/rss").toString()).block()).isEqualTo("feed");
            assertThat(server.getRequestCount()).isEqualTo(3);
        }
    }

    @Test
    void doesNotRetryPermanentClientErrorsAndMapsDetailsSafely() throws IOException {
        try (MockWebServer server = new MockWebServer()) {
            server.enqueue(new MockResponse().setResponseCode(404).setBody("secret response"));
            WebClientSourceDocumentLoader client = testClient();

            assertThatThrownBy(() -> client.load(
                                    server.url("/private?token=secret").toString())
                            .block())
                    .isInstanceOf(SourceIngestionException.class)
                    .hasMessageContaining("Unable to fetch source document from")
                    .hasMessageNotContaining("token=secret")
                    .hasMessageNotContaining("secret response");
            assertThat(server.getRequestCount()).isEqualTo(1);
        }
    }

    @Test
    void rejectsRedirectsAndEmptyDocuments() throws IOException {
        try (MockWebServer server = new MockWebServer()) {
            server.enqueue(new MockResponse().setResponseCode(302).addHeader("Location", "https://example.com"));
            server.enqueue(new MockResponse().setResponseCode(200).setBody("   "));
            WebClientSourceDocumentLoader client = testClient();

            assertThatThrownBy(() ->
                            client.load(server.url("/redirect").toString()).block())
                    .isInstanceOf(SourceIngestionException.class);
            assertThatThrownBy(
                            () -> client.load(server.url("/empty").toString()).block())
                    .isInstanceOf(SourceIngestionException.class)
                    .hasMessageContaining("empty");
            assertThat(server.getRequestCount()).isEqualTo(2);
        }
    }

    @Test
    void pinnedHttpsConnectionUsesOriginalHostnameForCertificateAndHostHeader() throws Exception {
        String hostname = "source-ingestion.invalid";
        HeldCertificate certificate = new HeldCertificate.Builder()
                .commonName(hostname)
                .addSubjectAlternativeName(hostname)
                .build();
        HandshakeCertificates serverCertificates =
                new HandshakeCertificates.Builder().heldCertificate(certificate).build();
        try (MockWebServer server = new MockWebServer()) {
            server.useHttps(serverCertificates.sslSocketFactory(), false);
            server.enqueue(new MockResponse().setResponseCode(200).setBody("secure feed"));
            server.start();
            PublicSourceUrlPolicy policy = pinnedLoopbackPolicy();
            var sslContext = SslContextBuilder.forClient()
                    .trustManager(certificate.certificate())
                    .build();
            WebClientSourceDocumentLoader client = new WebClientSourceDocumentLoader(
                    WebClient.builder(),
                    policy,
                    http -> http.secure(ssl -> ssl.sslContext(sslContext).handlerConfigurator(handler -> {
                        var parameters = handler.engine().getSSLParameters();
                        parameters.setEndpointIdentificationAlgorithm("HTTPS");
                        handler.engine().setSSLParameters(parameters);
                    })));

            String uri = "https://" + hostname + ":" + server.getPort() + "/feed";
            assertThat(client.load(uri).block()).isEqualTo("secure feed");
            assertThat(server.takeRequest().getHeader("Host")).isEqualTo(hostname + ":" + server.getPort());
        }
    }

    private static WebClientSourceDocumentLoader testClient() {
        return new WebClientSourceDocumentLoader(WebClient.builder(), pinnedLoopbackPolicy());
    }

    private static PublicSourceUrlPolicy pinnedLoopbackPolicy() {
        return new PublicSourceUrlPolicy() {
            @Override
            public Mono<ValidatedUrl> validate(String rawUrl) {
                try {
                    return Mono.just(new ValidatedUrl(URI.create(rawUrl), List.of(InetAddress.getLoopbackAddress())));
                } catch (Exception error) {
                    return Mono.error(error);
                }
            }
        };
    }
}
