# syntax=docker/dockerfile:1
# Proposed opt-in build; never used by production Compose.
FROM node:22.22.2-trixie-slim@sha256:961a65354946a04bbf2bfb3a1b25b53638a0e1fdb07ff56689955b9788400903 AS builder
WORKDIR /workspace/frontend/mission-planner
COPY frontend/mission-planner/package*.json ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm ci --engine-strict --strict-ssl=true --no-audit --no-fund
