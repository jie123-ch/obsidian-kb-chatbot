import re
import sqlite3

import numpy as np

import config
import embed

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def iter_markdown_files():
    """递归收集 vault 下所有 .md，排除插件/工具产物目录。"""
    for p in sorted(config.VAULT_PATH.rglob("*.md")):
        try:
            rel = p.relative_to(config.VAULT_PATH)
        except ValueError:
            continue
        if set(rel.parts) & set(config.EXCLUDE_DIRS):
            continue
        yield p, rel


def read_text(path):
    if path.stat().st_size == 0:
        return None
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None


def strip_frontmatter(text):
    if text.startswith("---"):
        m = re.match(r"^---\s*\n.*?\n---\s*\n?", text, re.DOTALL)
        if m:
            return text[m.end():]
    return text


def clean_obsidian(text):
    # [[name|alias]] / [[name]] -> alias 或 name
    return WIKILINK_RE.sub(lambda m: m.group(2) or m.group(1), text)


def parse_note(text):
    return clean_obsidian(strip_frontmatter(text))


def chunk_note(text):
    """先按标题切成节，每节超长再按滑动窗口切分（中文按字符数）。"""
    chunks = []
    cur_heading = ""
    cur = []

    def flush():
        if cur:
            body = "\n".join(cur).strip()
            if body:
                chunks.append((cur_heading, body))

    for line in text.splitlines():
        if line.startswith("#"):
            flush()
            cur_heading = line.lstrip("#").strip()
            cur = [line]
        else:
            cur.append(line)
    flush()

    out = []
    for heading, body in chunks:
        if len(body) <= config.CHUNK_SIZE:
            out.append((heading, body))
        else:
            start = 0
            while start < len(body):
                piece = body[start : start + config.CHUNK_SIZE]
                out.append((heading, piece))
                if start + config.CHUNK_SIZE >= len(body):
                    break
                start += config.CHUNK_SIZE - config.CHUNK_OVERLAP
    return out


def build():
    conn = sqlite3.connect(config.INDEX_DB)
    conn.execute("DROP TABLE IF EXISTS chunks")
    conn.execute("DROP TABLE IF EXISTS meta")
    conn.execute(
        """CREATE TABLE chunks (
            id INTEGER PRIMARY KEY,
            note_title TEXT,
            rel_path TEXT,
            chunk_index INTEGER,
            heading TEXT,
            text TEXT,
            embedding BLOB
        )"""
    )
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()

    rows_meta = []  # (note_title, rel_path, chunk_index, heading, body)
    embed_inputs = []  # 实际用于向量化的文本（含标题前缀）
    count_files = 0

    for path, rel in iter_markdown_files():
        text = read_text(path)
        if not text:
            continue
        count_files += 1
        parsed = parse_note(text)
        note_title = path.stem
        for i, (heading, body) in enumerate(chunk_note(parsed)):
            rows_meta.append((note_title, str(rel), i, heading, body))
            embed_inputs.append(f"{heading}\n{body}" if heading else body)

    print(f"已读取 {count_files} 个文件，切分为 {len(embed_inputs)} 个片段，开始本地向量化…")
    if not embed_inputs:
        print("没有可索引的文本，退出。")
        conn.close()
        return

    vectors = embed.embed_texts(embed_inputs)
    dim = int(vectors[0].shape[0])
    conn.execute("INSERT INTO meta(key, value) VALUES('dim', ?)", (str(dim),))
    conn.commit()

    for (note_title, rel_path, ci, heading, body), vec in zip(rows_meta, vectors):
        blob = np.asarray(vec, dtype=np.float32).tobytes()
        conn.execute(
            "INSERT INTO chunks(note_title, rel_path, chunk_index, heading, text, embedding)"
            " VALUES(?,?,?,?,?,?)",
            (note_title, rel_path, ci, heading, body, blob),
        )
    conn.commit()
    conn.close()
    print(f"索引完成：{len(embed_inputs)} 个片段，向量维度 {dim}，已写入 {config.INDEX_DB}")


if __name__ == "__main__":
    build()
