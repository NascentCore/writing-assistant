# 第一阶段: 构建前端
FROM node:18-alpine as frontend-builder
WORKDIR /app/frontend
# 复制前端项目文件
COPY frontend/package*.json ./
# 安装依赖
RUN yarn install
# 复制源代码
COPY frontend/ ./
# 构建前端项目
RUN yarn build

# 第二阶段: 构建后端
FROM python:3.9-bullseye
WORKDIR /app

# 安装系统依赖
RUN echo \
    "deb https://mirrors.aliyun.com/debian/ bullseye main non-free contrib\n" \
    "deb https://mirrors.aliyun.com/debian-security/ bullseye-security main\n" \
    "deb https://mirrors.aliyun.com/debian/ bullseye-updates main non-free contrib\n" \
    > /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 复制后端项目文件
COPY backend/requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host mirrors.aliyun.com \
        -r requirements.txt

# 复制后端源代码
COPY backend/ .

# 从前端构建阶段复制构建产物
COPY --from=frontend-builder /app/frontend/build /app/static

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 