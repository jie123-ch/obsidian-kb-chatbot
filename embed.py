from functools import lru_cache

import config

# fastembed 基于 onnxruntime，无需庞大的 PyTorch，CPU 推理快、体积小。
# 首次使用某模型时会自动下载（国内请先 set HF_ENDPOINT=https://hf-mirror.com）。


@lru_cache(maxsize=1)
def get_embedder():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=config.EMBEDDING_MODEL)


def embed_texts(texts):
    """对一批文本做本地向量化，返回 list[np.ndarray(1-D, float32)]。"""
    model = get_embedder()
    return list(model.embed(texts))
