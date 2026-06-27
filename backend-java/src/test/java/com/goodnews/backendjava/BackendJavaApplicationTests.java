package com.goodnews.backendjava;

import org.junit.jupiter.api.Test;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;

import static org.assertj.core.api.Assertions.assertThat;

class BackendJavaApplicationTests {

    @Test
    void contextLoadsWithJavaSideDefaults() {
        try (ConfigurableApplicationContext context = new SpringApplicationBuilder(loadApplicationClass())
            .web(WebApplicationType.NONE)
            .properties("spring.flyway.enabled=false")
            .run()) {
            Object properties = context.getBean(loadPropertiesClass());

            assertThat(readNestedValue(properties, "app", "environment")).isEqualTo("dev");
            assertThat(readNestedValue(properties, "app", "contentApiServiceHost")).isEqualTo("localhost");
            assertThat(readNestedValue(properties, "scheduler", "sourceSyncIntervalMinutes")).isEqualTo(30);
        }
    }

    private Class<?> loadApplicationClass() {
        return loadClass("com.goodnews.backendjava.BackendJavaApplication");
    }

    private Class<?> loadPropertiesClass() {
        return loadClass("com.goodnews.backendjava.config.GoodNewsProperties");
    }

    private Class<?> loadClass(String className) {
        try {
            return Class.forName(className);
        } catch (ClassNotFoundException exception) {
            throw new IllegalStateException("Missing class " + className, exception);
        }
    }

    private Object readNestedValue(Object target, String firstAccessor, String secondAccessor) {
        return invoke(invoke(target, firstAccessor), secondAccessor);
    }

    private Object invoke(Object target, String methodName) {
        try {
            return target.getClass().getMethod(methodName).invoke(target);
        } catch (ReflectiveOperationException exception) {
            throw new IllegalStateException("Failed to invoke " + methodName, exception);
        }
    }
}
