# syntax=docker/dockerfile:1
# Proposed opt-in build; never used by production Compose.
FROM node:22.22.2-trixie-slim@sha256:961a65354946a04bbf2bfb3a1b25b53638a0e1fdb07ff56689955b9788400903 AS builder
WORKDIR /workspace/frontend/mission-planner
COPY frontend/mission-planner/package*.json ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm ci --engine-strict --strict-ssl=true --no-audit --no-fund
COPY frontend/mission-planner/ ./
COPY .perf391/diagnostic/ /diagnostic/
COPY .perf391/vite.perf391.mjs ./vite.perf391.mjs
COPY .perf391/tsconfig.perf391.json ./tsconfig.perf391.json
ARG VITE_OVERVIEW_HISTORY_POLL_SECONDS=1
RUN ./node_modules/.bin/tsc --noEmit --incremental false -p tsconfig.perf391.json && \
    ./node_modules/.bin/vite build --config vite.perf391.mjs
FROM nginx:alpine@sha256:892bb2152464f0c5d8972593a5f5afaf8054552580b699d95f8ff4af08c2d33d
COPY --from=builder /workspace/frontend/mission-planner/dist/ /usr/share/nginx/html/
COPY frontend/mission-planner/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
# prepare.py appends exact role-specific required labels to a generated Dockerfile.
