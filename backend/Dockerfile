FROM sxwl-registry.cn-beijing.cr.aliyuncs.com/sxwl-ai/aieditor-base:0327

WORKDIR /app

# 复制 Python 应用和依赖
COPY app /app/
COPY requirements.txt /app/

# 安装 Python 依赖
RUN pip install --upgrade pip && \
    pip install -r /app/requirements.txt

# 暴露端口
EXPOSE 8000

# 使用进程管理工具启动服务
CMD ["sh", "-c", "PYTHONPATH=$PYTHONPATH:/ uvicorn app.main:app --host 0.0.0.0 --port 8000"]
