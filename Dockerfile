FROM eclipse-temurin:21-jre-alpine
RUN apk add --no-cache docker-cli && addgroup -g 10001 app && adduser -D -u 10001 -G app app
WORKDIR /app
RUN mkdir /app/data && chown -R app:app /app
COPY target/launchpad-1.0.0.jar /app/app.jar
USER 10001:10001
ENV BIND_ADDRESS=0.0.0.0 PORT=8088
EXPOSE 8088
ENTRYPOINT ["java", "-jar", "/app/app.jar"]