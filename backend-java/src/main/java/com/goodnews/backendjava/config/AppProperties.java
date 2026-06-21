package com.goodnews.backendjava.config;

public class AppProperties {

    private String environment = "dev";
    private String contentApiServiceHost = "localhost";
    private int contentApiServicePort = 8000;
    private int frontendPort = 5173;
    private String analysisServiceHost = "localhost";
    private int analysisServicePort = 8100;
    private String sourceIngestionServiceHost = "localhost";
    private int sourceIngestionServicePort = 8200;
    private String deliveryServiceHost = "localhost";
    private int deliveryServicePort = 8300;
    private String analysisStubResponseJson;
    private String ingestionResponsesJson;

    public String getEnvironment() {
        return environment;
    }

    public void setEnvironment(String environment) {
        this.environment = environment;
    }

    public String getContentApiServiceHost() {
        return contentApiServiceHost;
    }

    public void setContentApiServiceHost(String contentApiServiceHost) {
        this.contentApiServiceHost = contentApiServiceHost;
    }

    public int getContentApiServicePort() {
        return contentApiServicePort;
    }

    public void setContentApiServicePort(int contentApiServicePort) {
        this.contentApiServicePort = contentApiServicePort;
    }

    public int getFrontendPort() {
        return frontendPort;
    }

    public void setFrontendPort(int frontendPort) {
        this.frontendPort = frontendPort;
    }

    public String getAnalysisServiceHost() {
        return analysisServiceHost;
    }

    public void setAnalysisServiceHost(String analysisServiceHost) {
        this.analysisServiceHost = analysisServiceHost;
    }

    public int getAnalysisServicePort() {
        return analysisServicePort;
    }

    public void setAnalysisServicePort(int analysisServicePort) {
        this.analysisServicePort = analysisServicePort;
    }

    public String getSourceIngestionServiceHost() {
        return sourceIngestionServiceHost;
    }

    public void setSourceIngestionServiceHost(String sourceIngestionServiceHost) {
        this.sourceIngestionServiceHost = sourceIngestionServiceHost;
    }

    public int getSourceIngestionServicePort() {
        return sourceIngestionServicePort;
    }

    public void setSourceIngestionServicePort(int sourceIngestionServicePort) {
        this.sourceIngestionServicePort = sourceIngestionServicePort;
    }

    public String getDeliveryServiceHost() {
        return deliveryServiceHost;
    }

    public void setDeliveryServiceHost(String deliveryServiceHost) {
        this.deliveryServiceHost = deliveryServiceHost;
    }

    public int getDeliveryServicePort() {
        return deliveryServicePort;
    }

    public void setDeliveryServicePort(int deliveryServicePort) {
        this.deliveryServicePort = deliveryServicePort;
    }

    public String getAnalysisStubResponseJson() {
        return analysisStubResponseJson;
    }

    public void setAnalysisStubResponseJson(String analysisStubResponseJson) {
        this.analysisStubResponseJson = analysisStubResponseJson;
    }

    public String getIngestionResponsesJson() {
        return ingestionResponsesJson;
    }

    public void setIngestionResponsesJson(String ingestionResponsesJson) {
        this.ingestionResponsesJson = ingestionResponsesJson;
    }
}
