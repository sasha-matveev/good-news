FROM eclipse-temurin:21-jdk AS build
WORKDIR /build
COPY backend-java /build
RUN ./mvnw -B -pl application -am -DskipTests package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /build/application/target/good-news-application-0.0.1-SNAPSHOT-exec.jar /app/good-news-application.jar
ENTRYPOINT ["java", "-jar", "/app/good-news-application.jar"]
