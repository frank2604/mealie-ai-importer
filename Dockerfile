# Build stage
FROM node:20-alpine AS build
WORKDIR /app

# Install dependencies from the lockfile exactly (reproducible builds).
# `npm ci` pins every package to package-lock.json, so a rebuild can never
# silently pull a different (and possibly broken) dependency version.
COPY package*.json ./
RUN npm ci

# Build application.
# VITE_APP_VERSION is passed in from CI (commit SHA) so the running build is
# identifiable in the UI; defaults to "dev" for a plain local docker build.
ARG VITE_APP_VERSION=dev
ENV VITE_APP_VERSION=$VITE_APP_VERSION
COPY . .
RUN npm run build

# Runtime stage
FROM nginx:1.25-alpine

LABEL org.opencontainers.image.title="Mealie AI Importer UI"
LABEL org.opencontainers.image.description="Frontend for the Mealie AI Importer wizard"
LABEL org.opencontainers.image.version="0.1.0"

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
