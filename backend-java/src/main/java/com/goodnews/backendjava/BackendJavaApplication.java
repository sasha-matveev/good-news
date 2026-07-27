package com.goodnews.backendjava;

import com.goodnews.backendjava.config.DatabaseMigrationRunner;
import java.util.Arrays;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.context.ConfigurableApplicationContext;

@ConfigurationPropertiesScan
@SpringBootApplication
public class BackendJavaApplication {

    public static void main(String[] args) {
        if (Arrays.asList(args).contains("--good-news.migration.run=true")) {
            runDatabaseMigration(args);
            return;
        }
        SpringApplication.run(BackendJavaApplication.class, args);
    }

    private static void runDatabaseMigration(String[] args) {
        try (ConfigurableApplicationContext context = new SpringApplicationBuilder(BackendJavaApplication.class)
                .properties("spring.main.web-application-type=none")
                .run(args)) {
            context.getBean(DatabaseMigrationRunner.class).migrate();
        }
    }
}
