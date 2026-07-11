package com.goodnews.backendjava.ingestion.parsing;

import com.goodnews.backendjava.ingestion.model.CandidatePost;
import com.goodnews.backendjava.ingestion.model.PublicationDateSource;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.parser.Parser;
import org.springframework.stereotype.Component;

@Component
public final class FeedDocumentParser {
    private final PublicationDateParser dates;

    public FeedDocumentParser(PublicationDateParser dates) {
        this.dates = dates;
    }

    public List<CandidatePost> parse(String xml) {
        Document document = Jsoup.parse(xml, "", Parser.xmlParser());
        List<Element> items = document.select("item");
        if (items.isEmpty()) {
            items = document.select("entry");
        }
        List<CandidatePost> posts = new ArrayList<>();
        for (Element item : items) {
            String link = text(item, "link");
            Element linked = item.selectFirst("link[href]");
            if (link.isBlank() && linked != null) {
                link = linked.attr("href");
            }
            if (link.isBlank()) {
                continue;
            }
            String title = defaultValue(text(item, "title"), "Untitled post");
            String content = defaultValue(firstText(item, "description", "summary", "content"), title);
            Instant published = dates.parse(firstText(item, "pubDate", "published", "updated"));
            posts.add(new CandidatePost(
                    link.trim(),
                    Jsoup.parse(title).text(),
                    published,
                    stripBoilerplate(Jsoup.parse(content).text()),
                    published == null ? PublicationDateSource.NONE : PublicationDateSource.FEED));
        }
        return posts;
    }

    private static String text(Element parent, String selector) {
        Element value = parent.selectFirst(selector);
        return value == null ? "" : value.text();
    }

    private static String firstText(Element parent, String... selectors) {
        for (String selector : selectors) {
            String value = text(parent, selector);
            if (!value.isBlank()) {
                return value;
            }
        }
        return "";
    }

    private static String defaultValue(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    private static String stripBoilerplate(String value) {
        return value.replaceFirst(
                        "(?is)\\s*(The post .+? appeared first on .+?\\.|This post appeared first on .+?\\.)\\s*$", "")
                .trim();
    }
}
