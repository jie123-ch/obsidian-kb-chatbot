# 知识库服务器镜像
FROM python:3.13-slim

WORKDIR /app

# 让 fastembed 在国内/云环境顺利拉取中文嵌入模型
ENV HF_ENDPOINT=https://hf-mirror.com
ENV HF_HUB_DISABLE_XET=1
ENV PYTHONUNBUFFERED=1

# 固定 HuggingFace 缓存目录到镜像内路径：构建期预下载的嵌入模型，
# 运行期直接复用，避免云端实例冷启动时还要联网下载模型。
ENV HF_HOME=/app/.cache/huggingface
ENV HUGGINGFACE_HUB_CACHE=/app/.cache/huggingface

COPY requirements.txt .
# 腾讯云构建机访问 tuna 镜像返回 403，改用腾讯云内网 PyPI 镜像（并保留官方源兜底）
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.tencent.com/pypi/simple/ \
    --extra-index-url https://pypi.org/simple

COPY . .

# 预下载中文嵌入模型（BAAI/bge-small-zh-v1.5）；若构建机暂时无法访问镜像则跳过，
# 转由运行期首次查询时再下载（云端实例有外网出口，可访问 hf-mirror.com）。
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-zh-v1.5')" \
    || echo "warn: embedding model pre-download skipped, will fetch at runtime"

# kb.db 已预构建（随镜像打包），无需在容器里重建
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
