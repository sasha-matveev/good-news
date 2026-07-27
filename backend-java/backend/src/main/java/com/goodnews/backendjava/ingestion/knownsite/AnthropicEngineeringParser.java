package com.goodnews.backendjava.ingestion.knownsite;

import com.goodnews.backendjava.ingestion.parsing.PublicationDateParser;
import org.springframework.stereotype.Component;

@Component
public final class AnthropicEngineeringParser extends AbstractCardKnownSiteParser {
    public AnthropicEngineeringParser(PublicationDateParser dates) {
        super(dates);
    }

    @Override
    public String key() {
        return "anthropic_engineering";
    }

    @Override
    public String defaultListingUrl() {
        return "https://www.anthropic.com/engineering";
    }

    @Override
    protected String pathPrefix() {
        return "/engineering/";
    }

    @Override
    protected String expectedHost() {
        return "www.anthropic.com";
    }
}
