FROM docker.io/library/buildpack-deps@sha256:672aaedcfec98774308e902ae592697bc34b05d58f62104015cf3511f58e318a

COPY *.tar.xz /tmp/toolchains/
RUN set -eu; \
    for archive in /tmp/toolchains/*.tar.xz; do \
      directory="${archive%.tar.xz}"; \
      mkdir "$directory"; \
      tar -xJf "$archive" -C "$directory" --strip-components=1; \
      "$directory/install.sh" --prefix=/usr/local --disable-ldconfig; \
      rm -rf "$directory" "$archive"; \
    done; \
    test "$(rustc --version)" = "rustc 1.98.1 (48a229cea 2026-09-01)"; \
    test "$(cargo --version)" = "cargo 1.98.1 (797e8a9bc 2026-08-05)"; \
    cargo clippy --version; \
    cargo fmt --version

ENV PATH=/usr/local/bin:/usr/bin:/bin
USER 32768:32768
WORKDIR /source
ENTRYPOINT []
CMD []
