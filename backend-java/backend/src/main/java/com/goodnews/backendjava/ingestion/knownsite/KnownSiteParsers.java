package com.goodnews.backendjava.ingestion.knownsite;

import com.goodnews.backendjava.ingestion.application.SourceIngestionException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public final class KnownSiteParsers {
    private final Map<String, KnownSiteParser> parsers;

    public KnownSiteParsers(List<KnownSiteParser> parsers) {
        Map<String, KnownSiteParser> indexed = new HashMap<>();
        for (KnownSiteParser parser : parsers) {
            if (indexed.put(parser.key(), parser) != null) {
                throw new IllegalStateException("Duplicate known-site parser " + parser.key());
            }
        }
        this.parsers = Map.copyOf(indexed);
    }

    public KnownSiteParser resolve(String key) {
        KnownSiteParser parser = parsers.get(key);
        if (parser == null) {
            throw new SourceIngestionException("Unknown known-site parser '" + key + "'");
        }
        return parser;
    }
}
