# Multi-stage build for production
FROM node:22-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

ARG ACCEPTANCE_CANDIDATE_SHA
RUN test -n "$ACCEPTANCE_CANDIDATE_SHA"

# Copy source files
COPY . .

# Build for production
ARG VITE_OVERVIEW_HISTORY_POLL_SECONDS=1
RUN npm run build

# Production stage
FROM nginx:alpine

ARG ACCEPTANCE_CANDIDATE_SHA
RUN test -n "$ACCEPTANCE_CANDIDATE_SHA"
LABEL org.opencontainers.image.revision=$ACCEPTANCE_CANDIDATE_SHA

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
