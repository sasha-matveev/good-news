FROM eclipse-temurin:21-jdk AS build
WORKDIR /build
COPY backend-java /build
RUN ./mvnw -B -pl migration -am -DskipTests package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /build/migration/target/good-news-migration-0.0.1-SNAPSHOT-exec.jar /app/good-news-migration.jar
ENTRYPOINT ["java", "-jar", "/app/good-news-migration.jar"]
