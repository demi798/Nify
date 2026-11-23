# Nify 前端镜像：多阶段构建 + Nginx 托管静态资源并反代 /api
# 构建：docker build -t nify-frontend -f frontend/Dockerfile frontend/
# 运行时需能解析主机名 backend（Compose 服务名），或自行替换 nginx.conf 中的 upstream

# ---------- 构建阶段 ----------
FROM node:20-alpine AS build

WORKDIR /app

# 先装依赖以利用层缓存
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .

# 生产构建走同源 /api（由 Nginx 反代），勿指向 localhost
ENV VITE_API_BASE_URL=/api
RUN npm run build

# ---------- 运行阶段 ----------
FROM nginx:1.27-alpine AS runtime

# 去掉默认站点，使用项目配置
RUN rm -f /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d/nify.conf
COPY --from=build /app/dist /usr/share/nginx/html

# nginx 官方镜像以 root 起 master、worker 降权；对外 80
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
