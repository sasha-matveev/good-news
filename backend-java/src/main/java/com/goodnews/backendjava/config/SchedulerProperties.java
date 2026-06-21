package com.goodnews.backendjava.config;

public class SchedulerProperties {

    private int sourceSyncIntervalMinutes = 30;
    private int sourceFailureThreshold = 3;
    private String invoker;

    public int getSourceSyncIntervalMinutes() {
        return sourceSyncIntervalMinutes;
    }

    public void setSourceSyncIntervalMinutes(int sourceSyncIntervalMinutes) {
        this.sourceSyncIntervalMinutes = sourceSyncIntervalMinutes;
    }

    public int getSourceFailureThreshold() {
        return sourceFailureThreshold;
    }

    public void setSourceFailureThreshold(int sourceFailureThreshold) {
        this.sourceFailureThreshold = sourceFailureThreshold;
    }

    public String getInvoker() {
        return invoker;
    }

    public void setInvoker(String invoker) {
        this.invoker = invoker;
    }
}
