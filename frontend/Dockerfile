# ================================================
# MediaRefitAgent - 前端 Docker 配置
# ================================================
# 使用 Nginx 托管前端静态资源
# 注意：构建时需要先在宿主机构建前端，或使用多阶段构建
# ================================================

# ================================================
# 方式一：多阶段构建（推荐 - 单一命令完成）
# ================================================
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# ================================================
# Nginx 托管
# ================================================
FROM nginx:alpine

# 复制前端构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 Nginx 配置
COPY docker/nginx/frontend.conf /etc/nginx/conf.d/default.conf

EXPOSE 8083

CMD ["nginx", "-g", "daemon off;"]
