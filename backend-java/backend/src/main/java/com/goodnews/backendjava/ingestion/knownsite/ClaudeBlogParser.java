package com.goodnews.backendjava.ingestion.knownsite;

import com.goodnews.backendjava.ingestion.parsing.PublicationDateParser;
import org.springframework.stereotype.Component;

@Component
public final class ClaudeBlogParser extends AbstractCardKnownSiteParser {
    public ClaudeBlogParser(PublicationDateParser dates) {
        super(dates);
    }

    @Override
    public String key() {
        return "claude_blog";
    }

    @Override
    public String defaultListingUrl() {
        return "https://claude.com/blog";
    }

    @Override
    protected String pathPrefix() {
        return "/blog/";
    }

    @Override
    protected String expectedHost() {
        return "claude.com";
    }

    @Override
    protected boolean acceptsPath(String path) {
        return super.acceptsPath(path) && !path.startsWith("/blog/category/");
    }
}
