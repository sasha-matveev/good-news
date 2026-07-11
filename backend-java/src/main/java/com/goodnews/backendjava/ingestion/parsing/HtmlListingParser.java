package com.goodnews.backendjava.ingestion.parsing;

import com.goodnews.backendjava.ingestion.application.SourceIngestionException;
import com.goodnews.backendjava.ingestion.model.ListingCandidate;
import com.goodnews.backendjava.ingestion.model.PublicationDateSource;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Element;
import org.jsoup.select.Selector.SelectorParseException;
import org.springframework.stereotype.Component;

@Component
public final class HtmlListingParser {
    public List<ListingCandidate> parse(String html, String selector) {
        List<ListingCandidate> items = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        try {
            for (Element article : Jsoup.parse(html).select("article")) {
                Element link = article.selectFirst(selector);
                if (link == null || link.attr("href").isBlank() || !seen.add(link.attr("href"))) {
                    continue;
                }
                String title = link.text().trim();
                if (!title.isBlank()) {
                    items.add(new ListingCandidate(link.attr("href"), title, null, PublicationDateSource.NONE, null));
                }
            }
        } catch (SelectorParseException error) {
            throw new SourceIngestionException("Invalid HTML link selector '" + selector + "'", error);
        }
        return items;
    }
}
