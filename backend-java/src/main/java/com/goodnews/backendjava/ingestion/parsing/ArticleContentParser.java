package com.goodnews.backendjava.ingestion.parsing;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.goodnews.backendjava.ingestion.model.PublicationDateSource;
import java.time.Instant;
import java.util.List;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.springframework.stereotype.Component;

@Component
public final class ArticleContentParser {
    private final ObjectMapper objectMapper;
    private final PublicationDateParser dates;

    public ArticleContentParser(ObjectMapper objectMapper, PublicationDateParser dates) {
        this.objectMapper = objectMapper;
        this.dates = dates;
    }

    public ArticleContent parse(String html, String fallbackTitle) {
        Document document = Jsoup.parse(html);
        Element paragraph = document.selectFirst("p");
        String content = paragraph == null || paragraph.text().isBlank() ? fallbackTitle : paragraph.text();
        DateValue date = articleDate(document);
        return new ArticleContent(content, date.value(), date.source());
    }

    private DateValue articleDate(Document document) {
        for (Element script : document.select("script[type=application/ld+json]")) {
            try {
                JsonNode root = objectMapper.readTree(script.data());
                for (JsonNode node : root.isArray() ? root : List.of(root)) {
                    DateValue value = jsonDate(node);
                    if (value.value() != null) {
                        return value;
                    }
                }
            } catch (JsonProcessingException ignored) {
                // Malformed optional metadata must not discard a readable article.
            }
        }
        for (String property : List.of("article:published_time", "article:modified_time", "og:updated_time")) {
            DateValue value = meta(document, "property", property, PublicationDateSource.META_OG);
            if (value.value() != null) {
                return value;
            }
        }
        for (String name :
                List.of("date", "pubdate", "dc.date", "dc.date.issued", "published_time", "article.published")) {
            DateValue value = meta(document, "name", name, PublicationDateSource.META_DATE);
            if (value.value() != null) {
                return value;
            }
        }
        Element time = document.selectFirst("time[datetime]");
        Instant value = time == null ? null : dates.parse(time.attr("datetime"));
        return new DateValue(value, value == null ? PublicationDateSource.NONE : PublicationDateSource.TIME_ELEMENT);
    }

    private DateValue meta(Document document, String attribute, String key, PublicationDateSource source) {
        Element meta = document.selectFirst("meta[" + attribute + "='" + key + "'][content]");
        Instant value = meta == null ? null : dates.parse(meta.attr("content"));
        return new DateValue(value, value == null ? PublicationDateSource.NONE : source);
    }

    private DateValue jsonDate(JsonNode node) {
        if (node.isObject()) {
            for (String key : List.of("datePublished", "dateCreated", "dateModified")) {
                Instant value =
                        node.path(key).isTextual() ? dates.parse(node.path(key).asText()) : null;
                if (value != null) {
                    return new DateValue(value, PublicationDateSource.JSON_LD);
                }
            }
        }
        return new DateValue(null, PublicationDateSource.NONE);
    }

    public record ArticleContent(String rawContent, Instant publishedAt, PublicationDateSource publicationDateSource) {}

    private record DateValue(Instant value, PublicationDateSource source) {}
}
