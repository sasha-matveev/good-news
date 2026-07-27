package com.goodnews.backendjava.ingestion.knownsite;

import com.goodnews.backendjava.ingestion.application.SourceIngestionException;
import com.goodnews.backendjava.ingestion.model.ListingCandidate;
import com.goodnews.backendjava.ingestion.model.PublicationDateSource;
import com.goodnews.backendjava.ingestion.parsing.PublicationDateParser;
import java.net.URI;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Element;
import org.springframework.stereotype.Component;

@Component
public final class UberEngineeringParser implements KnownSiteParser {
    private final PublicationDateParser dates;

    public UberEngineeringParser(PublicationDateParser dates) {
        this.dates = dates;
    }

    @Override
    public String key() {
        return "uber_engineering";
    }

    @Override
    public String defaultListingUrl() {
        return "https://eng.uber.com";
    }

    @Override
    public List<ListingCandidate> parseListing(String html) {
        List<ListingCandidate> result = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        for (Element card : Jsoup.parse(html, defaultListingUrl()).select("a.blog-card[href]")) {
            String href = card.absUrl("href");
            URI uri;
            try {
                uri = URI.create(href);
            } catch (IllegalArgumentException error) {
                throw new SourceIngestionException("Known-site listing contains an invalid article URL", error);
            }
            if (!("eng.uber.com".equals(uri.getHost()) || "www.uber.com".equals(uri.getHost())) || !seen.add(href)) {
                continue;
            }
            Element heading = card.selectFirst("h3.blog-card-title");
            if (heading == null || heading.text().isBlank()) {
                continue;
            }
            Element excerpt = card.selectFirst("p.blog-card-excerpt");
            Instant date = dates.parse(card.attr("data-date"));
            String content = excerpt == null || excerpt.text().isBlank() ? heading.text() : excerpt.text();
            result.add(new ListingCandidate(
                    href,
                    heading.text(),
                    date,
                    date == null ? PublicationDateSource.NONE : PublicationDateSource.UBER_CARD,
                    content));
        }
        return result;
    }
}
