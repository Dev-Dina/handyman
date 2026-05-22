# Stage 1: build the React widget bundle
FROM node:20-alpine AS builder
WORKDIR /build
# Copy lock file first for layer caching
COPY widget/package.json widget/package-lock.json ./
RUN npm ci
COPY widget/ ./
RUN npm run build

# Stage 2: serve only the built dist/ via nginx under /widget-app/
# widget/dist/ is NOT committed — it is built here at image build time.
# Vite base='/widget-app/' so all asset references in index.html are absolute
# paths starting with /widget-app/assets/... which nginx serves from the
# widget-app/ subdirectory of its root.
FROM nginx:alpine
COPY --from=builder /build/dist /usr/share/nginx/html/widget-app/
COPY docker/nginx-widget.conf /etc/nginx/conf.d/default.conf
