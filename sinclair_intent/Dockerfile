ARG BUILD_FROM
FROM $BUILD_FROM

ARG TEMPIO_VERSION BUILD_ARCH
RUN \
    curl -sSLf -o /usr/bin/tempio \
    "https://github.com/home-assistant/tempio/releases/download/${TEMPIO_VERSION}/tempio_${BUILD_ARCH}"

RUN apk add --no-cache python3

COPY rootfs /

WORKDIR /app
RUN pip install -r requirements.txt
