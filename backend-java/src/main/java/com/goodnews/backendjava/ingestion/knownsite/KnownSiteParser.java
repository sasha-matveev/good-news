package com.goodnews.backendjava.ingestion.knownsite;

import com.goodnews.backendjava.ingestion.model.ListingCandidate;
import java.util.List;

public interface KnownSiteParser {
    String key();

    String defaultListingUrl();

    List<ListingCandidate> parseListing(String html);
}
