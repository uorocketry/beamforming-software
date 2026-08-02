FROM alpine:3.22

RUN apk add --no-cache can-utils iproute2

COPY simulation/canbus-entrypoint.sh /usr/local/bin/canbus-entrypoint
RUN chmod 0755 /usr/local/bin/canbus-entrypoint

ENTRYPOINT ["/usr/local/bin/canbus-entrypoint"]
