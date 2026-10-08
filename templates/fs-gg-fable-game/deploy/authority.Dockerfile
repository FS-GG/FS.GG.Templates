# syntax=docker/dockerfile:1.27
ARG ASPNET_RUNTIME_IMAGE=mcr.microsoft.com/dotnet/aspnet:11.0@sha256:0b9ad21f905462e6ab53320a6b69cfaceaac078a577c38bbeb6d47791556adb9
FROM ${ASPNET_RUNTIME_IMAGE}

ARG SVG_RELEASE_VERSION=workspace-v1
WORKDIR /app
COPY artifacts/releases/${SVG_RELEASE_VERSION}/authority-server/ ./

ENV ASPNETCORE_HTTP_PORTS=8080
EXPOSE 8080
USER $APP_UID
ENTRYPOINT ["dotnet", "Server.dll"]
