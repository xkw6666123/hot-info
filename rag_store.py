# -*- coding: utf-8 -*-
"""RAG 向量库：把博主真实转录向量化（GLM embedding-3），生成时按当前话题检索最相似的历史文案。

效果：不只像"这个博主"，还像"这个博主讲这类话题时"的样子。
设计：
- 向量库持久化到 transcript_vectors.json，**增量更新**（只 embed 新增转录，不重复花 token）
- 进程内缓存 store + 话题向量（同一话题 5 个博主只 embed 一次）
- 拿不到 key / API 失败 / 无候选 → 返回 []，上层自动回退"最新几条"
"""
import json, os, math

WORK = os.path.dirname(os.path.abspath(__file__))
ASR_FILE = os.path.join(WORK, "asr_content.json")
STORE_FILE = os.path.join(WORK, "transcript_vectors.json")
EMBED_URL = "https://open.bigmodel.cn/api/paas/v4/embeddings"
EMBED_MODEL = "embedding-3"
SCHEMA_V = 2   # 1=正文前1200字; 2=标题+正文前600字
TIMEOUT = 25

_STORE = None      # 进程内向量库缓存
_QCACHE = {}       # 话题 -> 向量 缓存（本次运行内）


def _load_key():
    for k in ("GLM_API_KEY", "ZHIPU_API_KEY"):
        v = os.environ.get(k, "").strip()
        if v:
            return v
    f = os.path.join(WORK, "glm_key.txt")
    if os.path.exists(f):
        try:
            return open(f, "r", encoding="utf-8").read().strip()
        except Exception:
            pass
    return ""


def _embed(text, key):
    import requests
    try:
        r = requests.post(EMBED_URL, json={"model": EMBED_MODEL, "input": text[:1500]},
                          headers={"Authorization": f"Bearer {key}",
                                   "Content-Type": "application/json"}, timeout=TIMEOUT)
        if r.status_code != 200:
            print(f"    ⚠️ embedding HTTP {r.status_code}: {r.text[:100]}", flush=True)
            return None
        return r.json()["data"][0]["embedding"]
    except Exception as e:
        print(f"    ⚠️ embedding 异常: {type(e).__name__}: {str(e)[:80]}", flush=True)
        return None


def _cosine(a, b):
    dot = na = nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0 or nb == 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def build_store():
    """增量构建/更新向量库：只为 asr_content.json 里新增的转录算向量。

    embedding 输入 = 标题 + 正文前段（标题是最强话题信号，正文补充语境）。
    SCHEMA_V 变更时自动全量重建（防止旧向量与新方案混用）。"""
    global _STORE
    key = _load_key()
    raw = {}
    if os.path.exists(STORE_FILE):
        try:
            raw = json.load(open(STORE_FILE, "r", encoding="utf-8"))
        except Exception:
            raw = {}
    # 带版本且版本一致 → 增量；否则（旧格式/无版本）→ 全量重建
    if isinstance(raw, dict) and raw.get("_v") == SCHEMA_V:
        store = raw.get("items", {})
        full_rebuild = False
    else:
        store = {}
        full_rebuild = True
    if key and os.path.exists(ASR_FILE):
        try:
            asr = json.load(open(ASR_FILE, "r", encoding="utf-8-sig"))
            items = asr.values() if isinstance(asr, dict) else asr
            added = 0
            for it in items:
                if not isinstance(it, dict):
                    continue
                aid = str(it.get("aweme_id") or it.get("url") or "")
                name = it.get("blogger_name", "")
                title = (it.get("title") or "").strip()
                ci = (it.get("content_intro") or "").strip()
                if not aid or not name or len(ci) < 120:
                    continue
                if aid in store and store[aid].get("vector"):
                    continue  # 已有向量，跳过（增量，不重复花 token）
                embed_input = f"{title}。{ci[:600]}" if title else ci[:600]
                vec = _embed(embed_input, key)
                if vec:
                    store[aid] = {"blogger": name, "text": ci, "title": title, "vector": vec}
                    added += 1
            if added:
                with open(STORE_FILE, "w", encoding="utf-8") as f:
                    json.dump({"_v": SCHEMA_V, "items": store}, f, ensure_ascii=False)
                tag = "全量重建" if full_rebuild else "新增"
                print(f"  📦 RAG 向量库: {tag} {added} 条向量，共 {len(store)} 条", flush=True)
        except Exception as e:
            print(f"    ⚠️ 构建向量库异常: {type(e).__name__}: {str(e)[:80]}", flush=True)
    _STORE = store
    return store


def get_store():
    global _STORE
    if _STORE is None:
        return build_store()
    return _STORE


def retrieve(blogger_name, topic, top_k=2):
    """检索该博主与当前话题最相似的 top_k 条历史转录。失败返回 []。"""
    global _QCACHE
    key = _load_key()
    if not key:
        return []
    store = get_store()
    cands = [v for v in store.values()
             if v.get("blogger") == blogger_name and v.get("vector") and v.get("text")]
    if not cands:
        return []
    if topic not in _QCACHE:
        _QCACHE[topic] = _embed(topic[:300], key)
    qvec = _QCACHE[topic]
    if not qvec:
        return [v["text"] for v in cands[-top_k:]]  # 查询向量失败 → 最新几条兜底
    scored = sorted(cands, key=lambda v: _cosine(qvec, v["vector"]), reverse=True)
    return [v["text"] for v in scored[:top_k]]


if __name__ == "__main__":
    # 自测：构建向量库 + 检索
    store = build_store()
    print(f"向量库共 {len(store)} 条")
    hits = retrieve("网吧信息差", "大学生毕业进厂打工引热议", top_k=2)
    print(f"检索到 {len(hits)} 条相似转录:")
    for h in hits:
        print("  ·", h[:70])
