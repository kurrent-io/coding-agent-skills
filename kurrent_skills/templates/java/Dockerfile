FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app

COPY pom.xml .
RUN mvn dependency:go-offline -B

COPY src ./src
RUN mvn package -DskipTests

FROM eclipse-temurin:17-jre
WORKDIR /app

COPY --from=build /app/target/kurrentdb-example-1.0-SNAPSHOT.jar app.jar

# Use environment variable for connection string
ENV KURRENTDB_CONNECTION_STRING=esdb://localhost:2113?tls=false

CMD ["java", "-jar", "app.jar"]
