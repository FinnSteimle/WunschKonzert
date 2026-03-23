# 1) Base dependencies stage (for shared cache)
FROM node:21-alpine AS base
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# 2) Test stage
FROM base AS test
COPY . .
# This stage is for running tests in an isolated container
# Usage: docker build --target test -t frontend-test . && docker run --network none frontend-test npm test

# 3) Build stage
FROM base AS build
ENV DOCKER_BUILD=true
COPY . .
RUN npm run build

# 4) Production dependencies stage
FROM node:21-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# 5) Runtime stage
FROM node:21-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY --from=build /app/build ./build
COPY --from=build /app/package.json ./package.json
USER node
EXPOSE 3000
CMD ["node", "build/index.js"]
