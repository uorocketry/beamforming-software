FROM ghcr.io/astral-sh/uv:0.12.1@sha256:cf4eedcaa81655197f625739489effcbe71b61ceb1506f332c3facae5deceded AS uv
FROM python:3.11.15-slim-bookworm

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /workspace

COPY pi /workspace/pi
RUN uv sync --project /workspace/pi --frozen --no-dev

COPY simulation /simulation
ENV PATH="/workspace/pi/.venv/bin:${PATH}"
