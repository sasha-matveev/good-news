FROM eclipse-temurin:21-jdk AS build
WORKDIR /build
COPY backend-java /build
RUN ./mvnw -B -pl contract -am -DskipTests package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /build/contract/target/good-news-contract-0.0.1-SNAPSHOT-exec.jar /app/good-news-contract.jar
ENTRYPOINT ["java", "-jar", "/app/good-news-contract.jar"]
