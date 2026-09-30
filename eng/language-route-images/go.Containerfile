FROM docker.io/library/debian@sha256:f3034a6ec3c1205360777c4aae76234998866ad18806ae62b63a3f84ccad782b

COPY go1.27.1.linux-amd64.tar.gz /tmp/go.tar.gz
RUN set -eu; \
    tar -xzf /tmp/go.tar.gz -C /usr/local; \
    rm /tmp/go.tar.gz; \
    test "$(/usr/local/go/bin/go version)" = "go version go1.27.1 linux/amd64"

ENV PATH=/usr/local/go/bin:/usr/bin:/bin
USER 32768:32768
WORKDIR /source
ENTRYPOINT []
CMD []
