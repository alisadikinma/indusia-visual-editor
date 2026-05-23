# Dual-target Dockerfile for the Vue 3 frontend.
#
# Dev build:        docker build --target dev     -t indusia-web:dev    -f web/Dockerfile web
# Production build: docker build --target runtime -t indusia-web:prod   -f web/Dockerfile web
#
# Production strategy: build the Vite SPA in a Node builder, then serve the
# resulting /dist tree from nginx:alpine. The runtime layer never contains
# Node or source code — only static assets + nginx config.

# ---------------- builder ----------------
FROM node:24-alpine AS builder

RUN corepack enable

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN corepack pnpm install --frozen-lockfile

COPY . .
RUN corepack pnpm build

# ---------------- dev ----------------
FROM node:24-alpine AS dev

RUN corepack enable
WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN corepack pnpm install --frozen-lockfile

COPY . .

EXPOSE 5173
CMD ["corepack", "pnpm", "dev", "--host", "0.0.0.0"]

# ---------------- runtime ----------------
FROM nginx:1.27-alpine AS runtime

# nginx:alpine ships a default server block at /etc/nginx/conf.d/default.conf.
# Replace with our SPA-aware config that falls back to index.html on 404 so
# the Vue router handles client-side routes.
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the built static assets. The Vite output dir is `dist/` by default.
COPY --from=builder /app/dist /usr/share/nginx/html

# nginx:alpine's stock image already runs the master as root + workers as
# `nginx` user. We expose 8080 instead of 80 so we can drop root entirely.
RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx \
 && touch /var/run/nginx.pid \
 && chown nginx:nginx /var/run/nginx.pid

USER nginx
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
