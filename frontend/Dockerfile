# 1) Build stage
FROM node:21-alpine AS build

WORKDIR /app
# Install full dependencies for build
COPY package.json package-lock.json ./
RUN npm ci

# Copy source
COPY . .

# Build the app
RUN npm run build


# 2) Production dependencies stage
FROM node:21-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev


# 3) Runtime stage
FROM node:21-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Copy production dependencies
COPY --from=deps /app/node_modules ./node_modules

# Copy build output and package metadata
COPY --from=build /app/build ./build
COPY --from=build /app/package.json ./package.json

# Use non root user
USER node

EXPOSE 3000

CMD ["node", "build/index.js"]
