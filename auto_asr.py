#!/usr/bin/env python3
"""
自动ASR文案检测与补提
1. 检测博主视频是否有完整文案
2. 缺失或不完整的自动调用local_asr.py提取
3. 提取完成后自动更新data.json
"""
import json
import os
import subprocess
import sys

# 配置
DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
LOCAL_ASR = os.path.join(os.path.dirname(__file__), "local_asr.py")

# 文案完整性阈值
MIN_CONTENT_LENGTH = 200  # 低于此长度视为不完整


def check_content_quality():
    """检测文案质量，返回需要补提的数量"""
    with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    bloggers = [a for a in data.get("articles", []) if a.get("source") == "blogger"]
    need_count = 0

    for b in bloggers:
        ci = b.get("content_intro", "")
        if not ci or len(ci) < MIN_CONTENT_LENGTH:
            need_count += 1

    return need_count


def main():
    """主函数：检测并补提文案"""
    # 检测需要补提的数量
    need_count = check_content_quality()

    if need_count == 0:
        print("✅ 所有博主文案完整，无需补提")
        return

    print(f"🎯 检测到 {need_count} 条需要补提的文案")
    print("📞 调用 local_asr.py 进行补提...")

    # 调用 local_asr.py 进行补提
    try:
        result = subprocess.run(
            [sys.executable, LOCAL_ASR],
            capture_output=True,
            text=True,
            timeout=600,
            env={**os.environ, "MIMO_API_KEY": os.environ.get("MIMO_API_KEY", "tp-ct56cpxdmbbfsvma531fntsj2ru0a3584nz44oh3hxzodh6z")}
        )
        print(result.stdout)
        if result.stderr:
            print(f"⚠️ stderr: {result.stderr}")
    except subprocess.TimeoutExpired:
        print("⚠️ ASR超时")
    except Exception as e:
        print(f"❌ ASR失败: {e}")

    # 再次检查
    remaining = check_content_quality()
    if remaining == 0:
        print("\n✅ 所有文案已补提完成")
    else:
        print(f"\n⚠️ 还有 {remaining} 条文案需要补提")


if __name__ == "__main__":
    main()
