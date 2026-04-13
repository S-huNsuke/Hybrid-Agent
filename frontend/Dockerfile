FROM node:20-alpine AS build

ARG VITE_API_BASE_URL=https://api:8000/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS runtime

ARG API_UPSTREAM=http://api:8000
RUN apk add --no-cache gettext

COPY nginx.conf /etc/nginx/conf.d/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

RUN envsubst '\$API_UPSTREAM' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf && \
    rm /etc/nginx/conf.d/default.conf.template

EXPOSE 80
