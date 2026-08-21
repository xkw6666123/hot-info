#!/usr/bin/env python3
"""用 funasr(paraformer-zh) 重转写全部博主视频（读 asr_temp 已下载的 wav），写回 data.json"""
import json, os, sys, time

WORK = os.path.dirname(os.path.abspath(__file__))
os.chdir(WORK)
DATA_FILE = os.path.join(WORK, "data.json")
TEMP = os.path.join(WORK, "asr_temp")


def main():
    from funasr import AutoModel
    model = AutoModel(model="paraformer-zh", vad_model="fsmn-vad", punc_model="ct-punc", disable_update=True)
    print("模型就绪", flush=True)

    with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    bloggers = [a for a in data.get("articles", []) if a.get("source") == "blogger"]
    done, skip = 0, 0
    for i, v in enumerate(bloggers):
        # 已有真实文案（≥200字）不覆盖，避免 funasr 结果覆盖人工/F2 文案
        if len(v.get("content_intro", "")) >= 200:
            print(f"[{i+1}/{len(bloggers)}] {v.get('blogger_name')} ⏭️ 已有文案，跳过", flush=True)
            skip += 1
            continue
        aid = v.get("aweme_id") or str(v.get("id"))
        wav = os.path.join(TEMP, f"w_{aid}.wav")
        if not (os.path.exists(wav) and os.path.getsize(wav) > 2000):
            print(f"[{i+1}/{len(bloggers)}] {v.get('blogger_name')} ⚠️ 无wav: {aid}", flush=True)
            skip += 1
            continue
        t0 = time.time()
        try:
            res = model.generate(input=wav, batch_size_s=300)
            text = res[0]["text"].strip() if res else ""
        except Exception as e:
            print(f"[{i+1}/{len(bloggers)}] {v.get('blogger_name')} ❌ {type(e).__name__}: {str(e)[:80]}", flush=True)
            skip += 1
            continue
        if len(text) < 20:
            print(f"[{i+1}/{len(bloggers)}] {v.get('blogger_name')} ⚠️ 过短({len(text)}字)", flush=True)
            skip += 1
            continue
        v["content_intro"] = text
        done += 1
        print(f"[{i+1}/{len(bloggers)}] {v.get('blogger_name')} ✅ {len(text)}字 ({time.time()-t0:.0f}s) {text[:36]}...", flush=True)
        with open(DATA_FILE + ".tmp", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(DATA_FILE + ".tmp", DATA_FILE)

    print(f"\n✅ 完成 {done} 条，跳过 {skip} 条", flush=True)


if __name__ == "__main__":
    main()
