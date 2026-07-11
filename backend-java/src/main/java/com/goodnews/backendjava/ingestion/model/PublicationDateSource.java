package com.goodnews.backendjava.ingestion.model;

public enum PublicationDateSource {
    NONE("none"),
    FEED("feed"),
    KNOWN_SITE_LISTING("known_site_listing"),
    UBER_CARD("uber_card"),
    JSON_LD("json_ld"),
    META_OG("meta_og"),
    META_DATE("meta_date"),
    TIME_ELEMENT("time_element");

    private final String persistedValue;

    PublicationDateSource(String persistedValue) {
        this.persistedValue = persistedValue;
    }

    public String persistedValue() {
        return persistedValue;
    }
}
