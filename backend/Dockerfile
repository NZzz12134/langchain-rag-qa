FROM python:3.11-slim

WORKDIR /app

# 系统依赖（pdf/docx 解析所需的最小集）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p storage/documents storage/chroma

EXPOSE 8000

# 单 worker：进程级 BM25 索引/信号量/嵌入式 Chroma 均按单进程设计；
# 多副本横向扩容时需 CHROMA_MODE=server（compose 已配置）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
