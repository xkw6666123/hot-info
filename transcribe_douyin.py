# -*- coding: utf-8 -*-
"""批量转写抖音博主视频（免登录）：按博主 post 接口拿音频地址映射 + detail 兜底，逐条下载转写写回。
断点续跑：已有真实文案（>=200字）自动跳过。"""
import json, os, sys, time
sys.stdout.reconfigure(encoding='utf-8')
import douyin_dl

WORK = os.path.dirname(os.path.abspath(__file__))
os.chdir(WORK)
DATA_FILE = os.path.join(WORK, "data.json")
TEMP = os.path.join(WORK, "asr_temp")
os.makedirs(TEMP, exist_ok=True)

# 抖音博主 sec_uid（与 generate_hot.py BLOGGER_SEC_UIDS 一致）
SEC_UIDS = {
    "网吧信息差": "MS4wLjABAAAAokpF28xzuEX1XD968NZhGTOytSqQbDBf0kPjRTeBtVyooNhnCicUdWZYMZh8oUpv",
    "阿七大型纪录片": "MS4wLjABAAAAptvL9jL0lV_qhvEnHAhZRs5yEekpupXZUwucqRqrhBvMv2XUWQgxBNMRwcIP6Evf",
    "陈先生": "MS4wLjABAAAAnusbdI9PboQ_wCdWkwe12i9evUts7z8ibbkOe6HVludyd3hGjDqKegLU8Bp7_5ZF",
    "人类观察菌": "MS4wLjABAAAA7ie_zvIQ19AWP_ZDg7heFEoQMAY3K3E9UOGYn_UKZzODbWxHxj5tnD3HGjg9sZlN",
}


def main():
    with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    dy = [a for a in data["articles"]
          if a.get("source") == "blogger" and "douyin" in (a.get("url") or "")]

    from funasr import AutoModel
    print("加载 funasr 模型...", flush=True)
    model = AutoModel(model="iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
                      vad_model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
                      punc_model="iic/punc_ct-transformer_cn-en-common-vocab471067-large", disable_update=True)
    try:
        from opencc import OpenCC
        cc = OpenCC("t2s")
    except Exception:
        cc = None

    dl = douyin_dl.DouyinDL()

    # 按博主拿 post 接口音频映射（缓存一次）
    url_map = {}
    for name, sec_uid in SEC_UIDS.items():
        print(f"抓取 {name} 音频映射...", flush=True)
        m = dl.audio_url_by_sec_uid(sec_uid, count=30)
        url_map.update(m)
        print(f"  → {len(m)} 条", flush=True)
        time.sleep(1)

    updated = 0
    skipped = 0
    failed = 0
    for i, a in enumerate(dy):
        name = a.get("blogger_name", "")
        aweme_id = str(a.get("aweme_id") or "")
        ci = a.get("content_intro", "") or ""
        if len(ci) >= 200 and not ci.startswith("📹"):
            skipped += 1
            continue

        audio_url = url_map.get(aweme_id, "")
        if not audio_url:
            # detail 兜底
            audio_url = dl.audio_url_by_aweme_id(aweme_id)
            time.sleep(1)

        if not audio_url:
            print(f"[{i+1}/{len(dy)}] {name} {aweme_id} ❌ 无音频地址", flush=True)
            failed += 1
            continue

        wav = os.path.join(TEMP, f"w_{aweme_id}.wav")
        if os.path.exists(wav) and os.path.getsize(wav) > 2000:
            pass  # 复用已有 wav
        else:
            wav = dl.download_audio(audio_url, wav)
            if not wav:
                print(f"[{i+1}/{len(dy)}] {name} {aweme_id} ❌ 下载失败", flush=True)
                failed += 1
                continue
            time.sleep(1)

        t0 = time.time()
        try:
            res = model.generate(input=wav, batch_size_s=300)
            text = (res[0].get("text") or "").strip() if res else ""
        except Exception as e:
            print(f"[{i+1}/{len(dy)}] {name} {aweme_id} ❌ 转写异常 {type(e).__name__}", flush=True)
            failed += 1
            continue
        if cc:
            try:
                text = cc.convert(text)
            except Exception:
                pass
        text = text.strip()
        if len(text) < 20:
            print(f"[{i+1}/{len(dy)}] {name} {aweme_id} ⚠️ 过短({len(text)}字)", flush=True)
            failed += 1
            continue
        a["content_intro"] = text[:5000]
        updated += 1
        print(f"[{i+1}/{len(dy)}] {name} {aweme_id} ✅ {len(text)}字 ({time.time()-t0:.0f}s)", flush=True)

    if updated:
        with open(DATA_FILE + ".tmp", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(DATA_FILE + ".tmp", DATA_FILE)

    print(f"\n✅ 完成：更新 {updated} 条，跳过 {skipped} 条，失败 {failed} 条", flush=True)


if __name__ == "__main__":
    main()
