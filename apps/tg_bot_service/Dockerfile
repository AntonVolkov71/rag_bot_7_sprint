# build stage
FROM gradle:8.7-jdk17 AS build
WORKDIR /home/gradle/src
COPY . .

RUN gradle clean build -x test

# run stage
FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /home/gradle/src/build/libs/*.jar /app/app.jar

ENV JAVA_OPTS=""
CMD ["sh", "-c", "java $JAVA_OPTS -jar /app/app.jar"]
