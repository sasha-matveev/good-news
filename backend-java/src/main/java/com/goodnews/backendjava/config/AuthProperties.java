package com.goodnews.backendjava.config;

public class AuthProperties {

    private String firebaseProjectId;
    private String allowedEmails = "";
    private String oidcAudience;

    public String getFirebaseProjectId() {
        return firebaseProjectId;
    }

    public void setFirebaseProjectId(String firebaseProjectId) {
        this.firebaseProjectId = firebaseProjectId;
    }

    public String getAllowedEmails() {
        return allowedEmails;
    }

    public void setAllowedEmails(String allowedEmails) {
        this.allowedEmails = allowedEmails;
    }

    public String getOidcAudience() {
        return oidcAudience;
    }

    public void setOidcAudience(String oidcAudience) {
        this.oidcAudience = oidcAudience;
    }
}
