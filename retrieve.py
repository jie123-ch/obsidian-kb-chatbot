import sqlite3

import numpy as np

import config
import embed

_cache = {"data": None, "mtime": 0}


def _load():
    db = config.INDEX_DB
    if not db.exists():
        return None
    mtime = db.stat().st_mtime
    if _cache["data"] is not None and _cache["mtime"] == mtime:
        return _cache["data"]

    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT note_title, rel_path, heading, text, embedding FROM chunks"
    ).fetchall()
    conn.close()
    if not rows:
        return None

    titles, rels, headings, texts, vecs = [], [], [], [], []
    for title, rel, heading, text, blob in rows:
        titles.append(title)
        rels.append(rel)
        headings.append(heading)
        texts.append(text)
        vecs.append(np.frombuffer(blob, dtype=np.float32))

    matrix = np.stack(vecs)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    matrix = matrix / np.clip(norms, 1e-9, None)

    data = {
        "matrix": matrix,
        "titles": titles,
        "rels": rels,
        "headings": headings,
        "texts": texts,
    }
    _cache["data"] = data
    _cache["mtime"] = mtime
    return data


def search(query, k=config.TOP_K, min_score=config.MIN_SCORE):
    """检索 top-k 上下文。

    先按相似度降序，依次加入；分数跌破 min_score 时立即停止。
    返回的列表已按相关度从高到低排序，最多 k 条；可能为空。
    """
    data = _load()
    if data is None:
        return []
    q = np.asarray(embed.embed_texts([query])[0], dtype=np.float32)
    q = q / np.linalg.norm(q)
    scores = data["matrix"] @ q
    order = np.argsort(-scores)
    results = []
    for i in order:
        sc = float(scores[i])
        if sc < min_score:
            break  # 已按降序，下面的只会更低，直接停止
        results.append(
            {
                "note_title": data["titles"][i],
                "rel_path": data["rels"][i],
                "heading": data["headings"][i],
                "text": data["texts"][i],
                "score": sc,
            }
        )
        if len(results) >= k:
            break
    return results


def reload():
    _cache["data"] = None
    _cache["mtime"] = 0
    return _load()


def get_note_text(rel_path):
    """按笔记相对路径取回原文。

    优先由调用方读取真实 .md 文件；若云端未挂载 vault 文件，
    则把索引库里该笔记的所有片段拼接返回，保证“看原文”可用。
    """
    data = _load()
    if data is None:
        return None
    parts = []
    for i, rel in enumerate(data["rels"]):
        if rel == rel_path:
            head = data["headings"][i]
            if head:
                parts.append(f"\n## {head}\n")
            parts.append(data["texts"][i])
    if not parts:
        return None
    return "\n".join(parts).strip()
