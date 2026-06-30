#!/usr/bin/env python3
"""
多平台爬虫集成
支持抖音、B站、微博、知乎等平台
"""
import json
import os
import re
import urllib.request
from datetime import datetime


def fetch_douyin_hot():
    """获取抖音热搜"""
    try:
        url = 'https://tenapi.cn/v2/douyinhot'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('code') == 200:
                return data.get('data', [])
    except Exception as e:
        print(f"  ⚠️ 抖音热搜获取失败: {e}")
    return []


def fetch_bilibili_hot():
    """获取B站热搜"""
    try:
        url = 'https://tenapi.cn/v2/bilibilihot'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('code') == 200:
                return data.get('data', [])
    except Exception as e:
        print(f"  ⚠️ B站热搜获取失败: {e}")
    return []


def fetch_weibo_hot():
    """获取微博热搜"""
    try:
        url = 'https://tenapi.cn/v2/weibohot'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('code') == 200:
                return data.get('data', [])
    except Exception as e:
        print(f"  ⚠️ 微博热搜获取失败: {e}")
    return []


def fetch_zhihu_hot():
    """获取知乎热榜"""
    try:
        url = 'https://tenapi.cn/v2/zhihuhot'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('code') == 200:
                return data.get('data', [])
    except Exception as e:
        print(f"  ⚠️ 知乎热榜获取失败: {e}")
    return []


def crawl_all_platforms():
    """爬取所有平台"""
    results = {}

    print("📡 爬取抖音热搜...")
    douyin = fetch_douyin_hot()
    results['抖音'] = douyin[:20] if douyin else []
    print(f"  ✅ 获取到 {len(results['抖音'])} 条")

    print("📡 爬取B站热搜...")
    bilibili = fetch_bilibili_hot()
    results['B站'] = bilibili[:20] if bilibili else []
    print(f"  ✅ 获取到 {len(results['B站'])} 条")

    print("📡 爬取微博热搜...")
    weibo = fetch_weibo_hot()
    results['微博'] = weibo[:20] if weibo else []
    print(f"  ✅ 获取到 {len(results['微博'])} 条")

    print("📡 爬取知乎热榜...")
    zhihu = fetch_zhihu_hot()
    results['知乎'] = zhihu[:20] if zhihu else []
    print(f"  ✅ 获取到 {len(results['知乎'])} 条")

    return results


def main():
    """主函数"""
    print("=== 多平台爬虫 ===\n")

    results = crawl_all_platforms()

    # 统计
    total = sum(len(v) for v in results.values())
    print(f"\n📊 爬取完成: {total} 条热点")

    # 保存结果
    output_file = os.path.join(os.path.dirname(__file__), '..', 'multi_platform_data.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"✅ 已保存到 {output_file}")

    # 显示统计
    for platform, items in results.items():
        if items:
            print(f"\n【{platform}】")
            for i, item in enumerate(items[:3], 1):
                title = item.get('name', item.get('title', ''))[:30]
                hot = item.get('hot', item.get('index', 0))
                print(f"  {i}. {title} (热度: {hot})")


if __name__ == "__main__":
    main()
