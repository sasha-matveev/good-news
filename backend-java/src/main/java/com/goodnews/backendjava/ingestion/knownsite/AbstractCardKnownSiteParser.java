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
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Element;

abstract class AbstractCardKnownSiteParser implements KnownSiteParser {
    private static final Pattern HUMAN_DATE = Pattern.compile(
            "\\b(?:Jan|Feb|Mar|Apr|May|Jun|June|Jul|July|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\\.?\\s+\\d{1,2},\\s+\\d{4}\\b",
            Pattern.CASE_INSENSITIVE);
    private final PublicationDateParser dates;

    AbstractCardKnownSiteParser(PublicationDateParser dates) {
        this.dates = dates;
    }

    protected abstract String pathPrefix();

    protected abstract String expectedHost();

    protected boolean acceptsPath(String path) {
        return path.startsWith(pathPrefix());
    }

    @Override
    public final List<ListingCandidate> parseListing(String html) {
        List<ListingCandidate> result = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        String selector = "article,[role=listitem],.w-dyn-item,.blog_list_item,.cms_blog_list_item,"
                + "[class*=__article],a[href^='" + pathPrefix() + "']";
        for (Element card : Jsoup.parse(html).select(selector)) {
            Element link = card.tagName().equals("a")
                    ? card
                    : card.selectFirst("a[href^='" + pathPrefix() + "'],a[href*='://'][href*='" + pathPrefix() + "']");
            if (link == null) {
                continue;
            }
            String href = link.attr("href");
            URI uri = parseExternalUri(href);
            String path = uri.getPath() == null ? href : uri.getPath();
            if (!acceptsPath(path)
                    || (uri.getHost() != null && !expectedHost().equalsIgnoreCase(uri.getHost()))
                    || !seen.add(href)) {
                continue;
            }
            Element heading = card.selectFirst("h1,h2,h3,h4");
            String title = (heading == null ? link.text() : heading.text()).trim();
            if (title.isBlank()) {
                continue;
            }
            Instant date = listingDate(card);
            result.add(new ListingCandidate(
                    href,
                    title,
                    date,
                    date == null ? PublicationDateSource.NONE : PublicationDateSource.KNOWN_SITE_LISTING,
                    null));
        }
        return result;
    }

    private Instant listingDate(Element card) {
        Element time = card.selectFirst("time");
        String candidate = time == null ? null : firstNonBlank(time.attr("datetime"), time.text());
        if (candidate == null) {
            Matcher matcher = HUMAN_DATE.matcher(card.text());
            candidate = matcher.find() ? matcher.group() : null;
        }
        return dates.parse(candidate);
    }

    private static String firstNonBlank(String first, String second) {
        return first == null || first.isBlank() ? second : first;
    }

    private static URI parseExternalUri(String href) {
        try {
            return URI.create(href);
        } catch (IllegalArgumentException error) {
            throw new SourceIngestionException("Known-site listing contains an invalid article URL", error);
        }
    }
}
