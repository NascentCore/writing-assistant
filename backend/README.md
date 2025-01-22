# AI Editor Backend

## 技术方案
- 使用 FastAPI 作为 Web 框架
- Python 3.8+
- uvicorn 作为 ASGI 服务器

## 部署
- 在backend目录下`cp .env.example .env`并修改为合适配置
- virtualenv
    - `python -m venv .venv`
    - `pip install -r requirements.txt`
    - `source .venv/bin/activate`
- 在backend目录下`export PYTHONPATH=$PYTHONPATH:$(pwd)`    
- 在backend/app/目录下执行`uvicorn main:app --reload`

## swagger
- http://localhost:8000/docs 
- http://localhost:8000/redoc