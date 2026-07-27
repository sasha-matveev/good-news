package com.goodnews.migration;

import com.goodnews.backendjava.config.GoodNewsProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.SpringBootConfiguration;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Import;

@SpringBootConfiguration
@EnableConfigurationProperties(GoodNewsProperties.class)
@Import(MigrationConfiguration.class)
public class MigrationApplication {

    public static void main(String[] args) {
        SpringApplication application = new SpringApplication(MigrationApplication.class);
        application.setWebApplicationType(WebApplicationType.NONE);
        application.run(args).close();
    }
}
