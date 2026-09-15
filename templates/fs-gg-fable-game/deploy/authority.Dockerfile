# syntax=docker/dockerfile:1.7
ARG ASPNET_RUNTIME_IMAGE=mcr.microsoft.com/dotnet/aspnet:10.0@sha256:6a94333d37514e385650a3c81a55e5350b67253dbe136e9cf17e499c35606a8c
FROM ${ASPNET_RUNTIME_IMAGE}

ARG SVG_RELEASE_VERSION=workspace-v1
WORKDIR /app
COPY artifacts/releases/${SVG_RELEASE_VERSION}/authority-server/ ./

ENV ASPNETCORE_HTTP_PORTS=8080
EXPOSE 8080
USER $APP_UID
ENTRYPOINT ["dotnet", "Server.dll"]
