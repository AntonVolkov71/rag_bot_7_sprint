plugins {
    application
    id("org.springframework.boot") version "3.2.2"
    id("io.spring.dependency-management") version "1.1.3"
    id("com.github.ben-manes.versions") version "0.48.0"

    id("io.freefair.lombok") version "8.6"
}


group = "ragbot"

version = "1.0-SNAPSHOT"

application { mainClass.set("ragbot.Application") }

repositories {
    mavenCentral()
}

dependencies {

    implementation("com.fasterxml.jackson.core:jackson-databind:2.15.2")
    implementation("org.springframework.boot:spring-boot-starter")
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.boot:spring-boot-devtools")
    implementation("net.datafaker:datafaker:2.0.1")
    implementation("org.telegram:telegrambots-spring-boot-starter:6.9.7.0")
}


