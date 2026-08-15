import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

VAULT_PATH = Path(os.getenv("VAULT_PATH", r"C:\Users\YourName\Documents\MyBrain"))
EXCLUDE_DIRS = [
    d.strip()
    for d in os.getenv("EXCLUDE_DIRS", ".obsidian,.copilot,copilot,.trash").split(",")
    if d.strip()
]

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")

INDEX_DB = BASE_DIR / os.getenv("INDEX_DB", "kb.db")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "700"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "120"))
TOP_K = int(os.getenv("TOP_K", "3"))
# 相似度阈值：低于此分视为噪声来源（如本次的"徐州地铁 0.481"被 0.49 砍掉）。
# bge-small-zh-v1.5 的实际分布：强相关 ≥0.55，弱相关 0.45-0.55，无关 <0.45。
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.49"))

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
DEEPSEEK_CHAT_URL = DEEPSEEK_BASE_URL + "/chat/completions"

# 多人/联网部署时的共享访问令牌。留空=不鉴权（仅本机开发用）。
# 部署到云后务必设置一个强随机值，客户端通过 ?token= 或 Authorization 头携带。
SERVER_TOKEN = os.getenv("SERVER_TOKEN", "")

# 让 fastembed 在本机/国内云都能顺利拉取中文嵌入模型
if not os.environ.get("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
if not os.environ.get("HF_HUB_DISABLE_XET"):
    os.environ["HF_HUB_DISABLE_XET"] = "1"
