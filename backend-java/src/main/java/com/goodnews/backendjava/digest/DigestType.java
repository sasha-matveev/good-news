package com.goodnews.backendjava.digest;

public enum DigestType {
    DAILY("daily"),
    WEEKLY("weekly"),
    OBSERVABILITY_DAILY("observability_daily");

    private final String databaseValue;

    DigestType(String databaseValue) {
        this.databaseValue = databaseValue;
    }

    public String databaseValue() {
        return databaseValue;
    }
}
