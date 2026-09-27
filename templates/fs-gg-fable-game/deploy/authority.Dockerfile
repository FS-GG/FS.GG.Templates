# syntax=docker/dockerfile:1.7
ARG ASPNET_RUNTIME_IMAGE=mcr.microsoft.com/dotnet/aspnet:10.0@sha256:2d584d8147faddb0d678c5748d47953e5b8e18621ed4fb7049a91381d9d7746f
FROM ${ASPNET_RUNTIME_IMAGE}

ARG SVG_RELEASE_VERSION=workspace-v1
WORKDIR /app
COPY artifacts/releases/${SVG_RELEASE_VERSION}/authority-server/ ./

ENV ASPNETCORE_HTTP_PORTS=8080
EXPOSE 8080
USER $APP_UID
ENTRYPOINT ["dotnet", "Server.dll"]
