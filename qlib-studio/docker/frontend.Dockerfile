# 构建阶段
FROM node:18-alpine AS build

WORKDIR /app
COPY package.json vite.config.js index.html ./
COPY src ./src

RUN npm install && npm run build

# 生产阶段
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

# Nginx 配置 - 支持 SPA 路由
RUN echo 'server { \
  listen 80; \
  server_name localhost; \
  root /usr/share/nginx/html; \
  index index.html; \
  \
  location /api { \
    proxy_pass http://backend:8000; \
    proxy_set_header Host $host; \
    proxy_set_header X-Real-IP $remote_addr; \
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; \
  } \
  \
  location / { \
    try_files $uri $uri/ /index.html; \
  } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
