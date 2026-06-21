package com.goodnews.backendjava;

import org.junit.jupiter.api.Test;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;

import static org.assertj.core.api.Assertions.assertThat;

class BackendJavaApplicationTests {

    @Test
    void contextLoads() {
        try (ConfigurableApplicationContext context = new SpringApplicationBuilder(loadApplicationClass())
            .web(WebApplicationType.NONE)
            .run()) {
            Object properties = context.getBean(loadPropertiesClass());

            assertThat(invoke(properties, "isLocalEnvironment")).isEqualTo(true);
            assertThat(readNestedValue(properties, "getApp", "getEnvironment")).isEqualTo("dev");
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

    private Object readNestedValue(Object target, String firstGetter, String secondGetter) {
        return invoke(invoke(target, firstGetter), secondGetter);
    }

    private Object invoke(Object target, String methodName) {
        try {
            return target.getClass().getMethod(methodName).invoke(target);
        } catch (ReflectiveOperationException exception) {
            throw new IllegalStateException("Failed to invoke " + methodName, exception);
        }
    }
}
