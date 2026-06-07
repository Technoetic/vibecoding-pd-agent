FROM python:3.12-slim
WORKDIR /app
COPY . .
# 의존성 0 — pip install 없음. PORT는 Railway가 주입(코드에서 os.environ 읽음).
CMD python server.py
