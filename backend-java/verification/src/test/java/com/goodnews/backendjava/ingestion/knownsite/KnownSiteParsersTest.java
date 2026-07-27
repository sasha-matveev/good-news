package com.goodnews.backendjava.ingestion.knownsite;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.goodnews.backendjava.ingestion.application.SourceIngestionException;
import com.goodnews.backendjava.ingestion.model.ListingCandidate;
import java.util.List;
import org.junit.jupiter.api.Test;

class KnownSiteParsersTest {
    @Test
    void resolvesRegisteredParser() {
        StubParser parser = new StubParser("site");
        assertThat(new KnownSiteParsers(List.of(parser)).resolve("site")).isSameAs(parser);
    }

    @Test
    void rejectsDuplicateRegistration() {
        assertThatThrownBy(() -> new KnownSiteParsers(List.of(new StubParser("site"), new StubParser("site"))))
                .isInstanceOf(IllegalStateException.class);
    }

    @Test
    void rejectsUnknownParser() {
        assertThatThrownBy(() -> new KnownSiteParsers(List.of()).resolve("missing"))
                .isInstanceOf(SourceIngestionException.class);
    }

    private record StubParser(String key) implements KnownSiteParser {
        @Override
        public String defaultListingUrl() {
            return "https://example.com";
        }

        @Override
        public List<ListingCandidate> parseListing(String html) {
            return List.of();
        }
    }
}
