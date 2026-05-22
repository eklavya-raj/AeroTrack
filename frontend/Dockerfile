# ---- Build Stage ----
FROM node:22-alpine AS build

WORKDIR /app

# Enable and install pnpm via corepack
RUN corepack enable && corepack prepare pnpm@latest --activate

# Copy package manifests first for better layer caching
COPY package.json pnpm-lock.yaml .npmrc* pnpm-workspace.yaml* ./
RUN pnpm install --frozen-lockfile

# Copy source code and build
COPY . .
RUN pnpm build

# ---- Production Stage ----
FROM nginx:alpine AS production

# Remove default nginx static content
RUN rm -rf /usr/share/nginx/html/*

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
