"""
热点信息差工具集
集成多个开源项目的功能
"""

from .hot_news_aggregator import aggregate_hot_news
from .multi_platform_crawler import crawl_all_platforms
from .cntext_analyzer import analyze_text, analyze_blogger_texts

__all__ = [
    'aggregate_hot_news',
    'crawl_all_platforms',
    'analyze_text',
    'analyze_blogger_texts',
]
