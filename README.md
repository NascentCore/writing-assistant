# 写作助手

```shell
git clone https://github.com/NascentCore/writing-assistant.git
```

## 前端
```shell
cd frontend

# 安装环境
yarn install

# 运行开发环境
yarn start
```

## 后端
```shell
cd backend

# 复制 backend 目录下的并修改为合适配置
cp .env.example app/.env

# 创建虚拟环境 virtualenv
python -m venv .venv
pip install -r requirements.txt
source .venv/bin/activate

## 运行环境
export PYTHONPATH=$PYTHONPATH:$(pwd)
cd app
uvicorn main:app --reload
```
