package com.goodnews.backendjava;

import static org.assertj.core.api.Assertions.assertThat;

import com.goodnews.backendjava.config.GoodNewsProperties;
import com.goodnews.migration.DatabaseMigrationRunner;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;

class GoodNewsApplicationTests {

    @Test
    void contextLoadsWithJavaSideDefaults() {
        try (ConfigurableApplicationContext context = new SpringApplicationBuilder(GoodNewsApplication.class)
                .web(WebApplicationType.NONE)
                .run()) {
            GoodNewsProperties properties = context.getBean(GoodNewsProperties.class);

            assertThat(properties.app().environment()).isEqualTo("dev");
            assertThat(properties.app().contentApiServiceHost()).isEqualTo("localhost");
            assertThat(properties.scheduler().sourceSyncIntervalMinutes()).isEqualTo(30);
            assertThat(context.getBeansOfType(Flyway.class)).isEmpty();
            assertThat(context.getBeansOfType(DatabaseMigrationRunner.class)).isEmpty();
        }
    }
}
