#!/usr/bin/env python3
"""只应用 asr_fixes.json 修复表到博主文案，不做其他后处理（避免 reprocess 副作用）。"""
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8')

WORK = os.path.dirname(os.path.abspath(__file__))
os.chdir(WORK)
DATA = os.path.join(WORK, "data.json")
FIXES = os.path.join(WORK, "asr_fixes.json")

# 加载修复表
fdata = json.load(open(FIXES, encoding="utf-8"))
clean_fixes = [tuple(x) for x in fdata.get("asr_fixes", [])]
zhe = [tuple(x) for x in fdata.get("zhe_to_zhe", [])]

# 繁转简（可选）
_cc = None
try:
    from opencc import OpenCC
    _cc = OpenCC("t2s")
except Exception:
    pass

data = json.load(open(DATA, encoding="utf-8-sig"))
changed = 0
for a in data.get("articles", []):
    if a.get("source") != "blogger":
        continue
    ci = a.get("content_intro", "") or ""
    if not ci:
        continue
    orig = ci
    if _cc:
        try:
            ci = _cc.convert(ci)
        except Exception:
            pass
    for w, r in zhe:
        ci = ci.replace(w, r)
    for w, r in clean_fixes:
        ci = ci.replace(w, r)
    if ci != orig:
        a["content_intro"] = ci.strip()
        changed += 1
        # 打印差异，便于核对
        print(f"  修复 {a.get('blogger_name')} {a.get('date')}: {orig[:15]} → {ci.strip()[:15]}")

json.dump(data, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"\n✅ 应用修复表完成，{changed} 条文案有变化")
