FROM node:18 AS builder

WORKDIR /app

# 复制 package.json 和 yarn.lock 并安装依赖
COPY package.json ./
RUN yarn install --frozen-lockfile

# 复制项目代码并构建
COPY . ./
RUN yarn build

# 使用 nginx 作为 Web 服务器
FROM nginx:1.25-alpine

# 删除默认的 nginx 配置
RUN rm -rf /etc/nginx/conf.d/*

# 复制自定义的 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制构建好的前端代码到 nginx 目录
COPY --from=builder /app/build /usr/share/nginx/html

# 暴露端口
EXPOSE 80

# 启动 nginx
CMD ["nginx", "-g", "daemon off;"]
