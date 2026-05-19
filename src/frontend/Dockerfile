# Build stage
FROM node:20-alpine AS build

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Receive the build arg from compose
ARG VITE_CONFIG_API_URL
# Write it to .env.production so Vite picks it up during build
RUN echo "VITE_CONFIG_API_URL=$VITE_CONFIG_API_URL" > .env.production

# Build the app
RUN npm run build

# Serve stage
FROM nginx:alpine


# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx config template
COPY nginx.conf /etc/nginx/conf.d/default.conf