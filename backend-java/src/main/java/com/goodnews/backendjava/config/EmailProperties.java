package com.goodnews.backendjava.config;

public class EmailProperties {

    private String appMasterKey;
    private String publicContentApiOrigin;
    private String publicFrontendOrigin;

    public String getAppMasterKey() {
        return appMasterKey;
    }

    public void setAppMasterKey(String appMasterKey) {
        this.appMasterKey = appMasterKey;
    }

    public String getPublicContentApiOrigin() {
        return publicContentApiOrigin;
    }

    public void setPublicContentApiOrigin(String publicContentApiOrigin) {
        this.publicContentApiOrigin = publicContentApiOrigin;
    }

    public String getPublicFrontendOrigin() {
        return publicFrontendOrigin;
    }

    public void setPublicFrontendOrigin(String publicFrontendOrigin) {
        this.publicFrontendOrigin = publicFrontendOrigin;
    }
}
