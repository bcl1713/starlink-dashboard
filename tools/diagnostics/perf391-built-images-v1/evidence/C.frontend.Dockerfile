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

LABEL diagnostic="true"
LABEL org.opencontainers.image.revision="ee9ce1010e72e83cb6d4b8c79ecc15091b9d8832"
LABEL base_application_sha="ee9ce1010e72e83cb6d4b8c79ecc15091b9d8832"
LABEL integration_source_sha="051870c738d9ab72338852ea848918a35a663094"
LABEL collector_source_sha="a48837b99d87366c6e3fc24ba2915f0b739cddad"
LABEL patch_sha256="b0886cc70df5811670f43e455cd8917b641d42a09c320bb378cb5df85be26c3c"
LABEL effective_source_sha256="4f1913894101595ab96bdd289bd80f88a6dcb95c058d0851cb3e4e025ae13f4a"
LABEL frontend_patch_sha256="e744be0f260e77799d55c6c4f9f23e8a65d9fd793e9eb164c13a21f156e44551"
LABEL collector_release_sha="c47d21e3c5bbf92189afbf291b73b9da7a035a4b"
LABEL frozen_harness_sha="f3029024b5950a267645195476da5cbca326f16a"
LABEL runtime_overlay_sha256="5b3b36938d43d5ade1b9bb67d32dd6bf36b5f80d8f298b475ef732e794ba965c"
LABEL perf391.role="C"
LABEL runtime_frontend_closure_sha256="5dcf2b6ace61440516fc695f4bcab4d8da487e0612f80a864dd6669bab641695"
