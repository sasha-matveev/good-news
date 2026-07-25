FROM eclipse-temurin:21-jdk AS build
WORKDIR /build
COPY backend-java /build
RUN ./mvnw -B -DskipTests package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /build/target/backend-java-0.0.1-SNAPSHOT.jar /app/backend-java.jar
ENTRYPOINT ["java", "-jar", "/app/backend-java.jar"]

