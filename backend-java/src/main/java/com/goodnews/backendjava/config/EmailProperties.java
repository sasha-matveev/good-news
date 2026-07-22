package com.goodnews.backendjava.config;

import java.time.Duration;
import org.springframework.boot.context.properties.bind.ConstructorBinding;
import org.springframework.boot.context.properties.bind.DefaultValue;

public record EmailProperties(
        String appMasterKey,
        String publicContentApiOrigin,
        String publicFrontendOrigin,
        @DefaultValue("10s") Duration smtpConnectionTimeout,
        @DefaultValue("30s") Duration smtpReadTimeout,
        @DefaultValue("30s") Duration smtpWriteTimeout) {

    @ConstructorBinding
    public EmailProperties {}

    public EmailProperties(String appMasterKey, String publicContentApiOrigin, String publicFrontendOrigin) {
        this(
                appMasterKey,
                publicContentApiOrigin,
                publicFrontendOrigin,
                Duration.ofSeconds(10),
                Duration.ofSeconds(30),
                Duration.ofSeconds(30));
    }
}
