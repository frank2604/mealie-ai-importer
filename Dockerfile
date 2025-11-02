# Build stage
FROM node:20-alpine AS build
WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Build application
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
