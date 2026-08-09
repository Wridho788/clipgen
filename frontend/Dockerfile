FROM node:22-alpine AS base

WORKDIR /app
RUN corepack enable

FROM base AS dependencies

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY frontend/package.json frontend/package.json
RUN pnpm install --frozen-lockfile

FROM dependencies AS build

COPY frontend frontend
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN pnpm -C frontend build

FROM node:22-alpine AS runner

WORKDIR /app/frontend
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Next's standalone tracing is unreliable with the Windows pnpm workspace used
# by this project. Keep the runtime deterministic by carrying the built app and
# its already-resolved workspace dependencies into the final local image.
COPY --from=build --chown=node:node /app/node_modules /app/node_modules
COPY --from=build --chown=node:node /app/frontend ./

USER node
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000').then((response) => process.exit(response.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "./node_modules/next/dist/bin/next", "start", "-p", "3000"]
