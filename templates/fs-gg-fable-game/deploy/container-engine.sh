#!/usr/bin/env bash

# Source this file after enabling `set -euo pipefail`. Podman is preferred for
# generated workspaces; Docker remains a supported Compose-spec runner and is
# used by GitHub-hosted qualification where it is already provisioned.
select_compose_engine() {
  local requested="${CONTAINER_ENGINE:-}"
  if [[ -n "$requested" ]]; then
    case "$requested" in
      podman)
        command -v podman >/dev/null || { echo "container edge: requested podman is unavailable" >&2; return 1; }
        podman compose version >/dev/null || { echo "container edge: podman compose provider is unavailable" >&2; return 1; }
        COMPOSE_ENGINE=(podman compose)
        ;;
      docker)
        command -v docker >/dev/null || { echo "container edge: requested docker is unavailable" >&2; return 1; }
        docker compose version >/dev/null || { echo "container edge: docker compose plugin is unavailable" >&2; return 1; }
        COMPOSE_ENGINE=(docker compose)
        ;;
      *)
        echo "container edge: CONTAINER_ENGINE must be podman or docker" >&2
        return 1
        ;;
    esac
  elif command -v podman >/dev/null && podman compose version >/dev/null 2>&1; then
    COMPOSE_ENGINE=(podman compose)
  elif command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
    COMPOSE_ENGINE=(docker compose)
  else
    echo "container edge: install Podman with a Compose provider, or Docker with its Compose plugin" >&2
    return 1
  fi
}
