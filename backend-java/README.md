# backend-java observability

The backend exposes these unauthenticated Actuator endpoints on the main application port:

- `/actuator/health`
- `/actuator/prometheus`

Quick verification from the repo root:

```powershell
mvn -f backend-java\pom.xml test
```

Manual endpoint check on the default application port:

```powershell
mvn -f backend-java\pom.xml spring-boot:run
curl.exe http://127.0.0.1:8080/actuator/health
curl.exe http://127.0.0.1:8080/actuator/prometheus
```
