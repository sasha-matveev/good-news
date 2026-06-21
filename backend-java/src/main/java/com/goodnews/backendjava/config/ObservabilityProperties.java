package com.goodnews.backendjava.config;

public class ObservabilityProperties {

    private String grafanaOrigin;
    private String grafanaHost = "127.0.0.1";
    private int grafanaHostPort = 3000;
    private String dailyReportTime = "18:00";

    public String getGrafanaOrigin() {
        return grafanaOrigin;
    }

    public void setGrafanaOrigin(String grafanaOrigin) {
        this.grafanaOrigin = grafanaOrigin;
    }

    public String getGrafanaHost() {
        return grafanaHost;
    }

    public void setGrafanaHost(String grafanaHost) {
        this.grafanaHost = grafanaHost;
    }

    public int getGrafanaHostPort() {
        return grafanaHostPort;
    }

    public void setGrafanaHostPort(int grafanaHostPort) {
        this.grafanaHostPort = grafanaHostPort;
    }

    public String getDailyReportTime() {
        return dailyReportTime;
    }

    public void setDailyReportTime(String dailyReportTime) {
        this.dailyReportTime = dailyReportTime;
    }
}
