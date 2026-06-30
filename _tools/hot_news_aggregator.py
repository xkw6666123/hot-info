#!/usr/bin/env python3
"""
热点新闻聚合器
集成多个平台的热点数据
"""
import json
import os
import urllib.request
from datetime import datetime

# 热点API
HOT_APIS = {
    '百度热搜': 'https://tenapi.cn/v2/baiduhot',
    '微博热搜': 'https://tenapi.cn/v2/weibohot',
    '知乎热榜': 'https://tenapi.cn/v2/zhihuhot',
    'B站热搜': 'https://tenapi.cn/v2/bilibilihot',
    '抖音热搜': 'https://tenapi.cn/v2/douyinhot',
}


def fetch_hot_news(platform, api_url):
    """获取热点新闻"""
    try:
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('code') == 200:
                return data.get('data', [])
    except Exception as e:
        print(f"  ⚠️ {platform} 获取失败: {e}")
    return []


def aggregate_hot_news():
    """聚合所有平台热点"""
    all_news = []

    for platform, api_url in HOT_APIS.items():
        print(f"📡 获取 {platform}...")
        news = fetch_hot_news(platform, api_url)
        if news:
            for item in news[:10]:  # 每个平台取前10条
                all_news.append({
                    'title': item.get('name', item.get('title', '')),
                    'hot': item.get('hot', item.get('index', 0)),
                    'url': item.get('url', ''),
                    'source': platform,
                    'fetched_at': datetime.now().isoformat(),
                })
            print(f"  ✅ 获取到 {len(news)} 条")
        else:
            print(f"  ⚠️ 无数据")

    return all_news


def main():
    """主函数"""
    print("=== 热点新闻聚合 ===\n")

    news = aggregate_hot_news()

    if news:
        print(f"\n📊 聚合完成: {len(news)} 条热点")

        # 按热度排序
        news.sort(key=lambda x: x.get('hot', 0), reverse=True)

        # 保存结果
        output_file = os.path.join(os.path.dirname(__file__), '..', 'hot_news_aggregated.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(news, f, ensure_ascii=False, indent=2)

        print(f"✅ 已保存到 {output_file}")

        # 显示前10条
        print("\n🔥 TOP 10 热点:")
        for i, item in enumerate(news[:10], 1):
            print(f"  {i}. [{item['source']}] {item['title']} (热度: {item['hot']})")
    else:
        print("⚠️ 没有获取到热点数据")


if __name__ == "__main__":
    main()
