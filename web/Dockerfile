# Dev image for the Vue 3 frontend. NOT production — M14 ships a multi-stage
# build with nginx + asset caching. This one just runs `pnpm dev` for HMR.
FROM node:24-alpine AS dev

RUN corepack enable

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN corepack pnpm install --frozen-lockfile

COPY . .

EXPOSE 5173

CMD ["corepack", "pnpm", "dev", "--host", "0.0.0.0"]
