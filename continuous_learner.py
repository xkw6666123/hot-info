#!/usr/bin/env python3
"""
持续学习系统
1. 归档所有ASR文案到永久存储
2. 每次运行时重新学习风格
3. 生成更真实的灵感内容
"""
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
ARCHIVE_FILE = os.path.join(os.path.dirname(__file__), "blogger_content_archive.json")
STYLE_FILE = os.path.join(os.path.dirname(__file__), "deep_style_learned.json")


def load_archive():
    """加载归档数据"""
    if os.path.exists(ARCHIVE_FILE):
        with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_archive(archive):
    """保存归档数据（原子写入）"""
    base = os.path.basename(ARCHIVE_FILE)
    tmp = os.path.join(os.getcwd(), base + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ARCHIVE_FILE)


def save_style(styles):
    """保存学习结果（原子写入）"""
    base = os.path.basename(STYLE_FILE)
    tmp = os.path.join(os.getcwd(), base + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(styles, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STYLE_FILE)


def archive_content():
    """将当前data.json中的博主文案归档到永久存储"""
    with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    archive = load_archive()
    new_count = 0

    for a in data.get("articles", []):
        if a.get("source") != "blogger":
            continue

        ci = a.get("content_intro", "")
        if len(ci) < 100:
            continue

        aweme_id = a.get("aweme_id", "")
        if not aweme_id:
            continue

        # 如果该视频还没有归档，或者新文案更长，则更新
        if aweme_id not in archive or len(ci) > len(archive[aweme_id].get("content_intro", "")):
            archive[aweme_id] = {
                "content_intro": ci,
                "blogger_name": a.get("blogger_name", ""),
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "date": a.get("date", ""),
                "archived_at": datetime.now().isoformat(),
            }
            new_count += 1

    save_archive(archive)
    print(f"📦 归档完成: {len(archive)} 条文案 (新增 {new_count} 条)")
    return archive


def extract_sentence_patterns(text):
    """提取句式模板"""
    patterns = []
    sentences = re.split(r'[。！？]', text)
    for s in sentences:
        s = s.strip()
        if len(s) < 5 or len(s) > 100:
            continue
        pattern = s
        pattern = re.sub(r'\d+', '{数字}', pattern)
        pattern = re.sub(r'\d{4}年\d{1,2}月\d{1,2}日', '{日期}', pattern)
        pattern = re.sub(r'\d{1,2}月\d{1,2}日', '{日期}', pattern)
        patterns.append(pattern)
    return patterns


def extract_vocabulary(text):
    """提取词汇库"""
    words = {
        'transitions': [],
        'emotions': [],
        'interactions': [],
        'connectors': [],
    }

    transition_words = re.findall(r'不过|但是|其实|说实话|说真的|讲真的|说白了|说到底|归根结底|换句话说|虽然|可是|然而', text)
    words['transitions'].extend(transition_words)

    emotion_words = re.findall(r'离谱|逆天|炸裂|惊呆|笑死|怒了|崩溃|破防|绷不住|绝了|牛|厉害|可怕|恐怖|搞笑|有意思|奇葩|迷惑|震惊|意外', text)
    words['emotions'].extend(emotion_words)

    interaction_words = re.findall(r'你们|大家|网友|评论区|点赞|分享|关注|觉得|认为|怎么看|遇到过|见过|来', text)
    words['interactions'].extend(interaction_words)

    connector_words = re.findall(r'首先|然后|接着|最后|一方面|另一方面|不仅|而且|因为|所以|如果|就|才|也|还|又|再', text)
    words['connectors'].extend(connector_words)

    return words


def extract_opening_ending(text):
    """提取开头和结尾"""
    openings = []
    endings = []
    sentences = re.split(r'[。！？]', text)

    for s in sentences[:3]:
        s = s.strip()
        if len(s) >= 10:
            openings.append(s[:30])

    for s in sentences[-3:]:
        s = s.strip()
        if len(s) >= 10:
            endings.append(s[-30:])

    return openings, endings


def learn_from_archive():
    """从归档数据中学习风格"""
    archive = load_archive()
    if not archive:
        print("⚠️ 归档数据为空")
        return {}

    # 按博主分组
    blogger_texts = defaultdict(list)
    for aweme_id, item in archive.items():
        name = item.get("blogger_name", "")
        ci = item.get("content_intro", "")
        if name and ci and len(ci) > 100:
            blogger_texts[name].append(ci)

    # 学习每位博主的风格
    styles = {}
    for name, texts in blogger_texts.items():
        all_patterns = []
        all_words = defaultdict(list)
        all_openings = []
        all_endings = []

        for text in texts:
            patterns = extract_sentence_patterns(text)
            all_patterns.extend(patterns)

            words = extract_vocabulary(text)
            for k, v in words.items():
                all_words[k].extend(v)

            openings, endings = extract_opening_ending(text)
            all_openings.extend(openings)
            all_endings.extend(endings)

        if not all_patterns:
            continue

        # 统计高频特征
        pattern_counts = Counter(all_patterns)
        top_patterns = [p for p, c in pattern_counts.most_common(20) if c >= 1]

        word_stats = {}
        for k, v in all_words.items():
            word_counts = Counter(v)
            word_stats[k] = [w for w, c in word_counts.most_common(15)]

        opening_counts = Counter(all_openings)
        ending_counts = Counter(all_endings)

        styles[name] = {
            "blogger": name,
            "sample_count": len(texts),
            "sentence_patterns": top_patterns[:15],
            "vocabulary": word_stats,
            "top_openings": [p for p, c in opening_counts.most_common(8)],
            "top_endings": [p for p, c in ending_counts.most_common(8)],
            "avg_length": sum(len(t) for t in texts) // len(texts),
            "last_updated": datetime.now().isoformat(),
        }

        print(f"✅ {name}: {len(texts)}条样本, 平均{styles[name]['avg_length']}字")

    save_style(styles)

    print(f"\n📚 学习完成: {len(styles)} 位博主")
    return styles


def generate_inspiration(topic, source, styles):
    """基于学习到的风格生成灵感"""
    def pick(patterns, seed):
        if not patterns:
            return ""
        return patterns[abs(hash(seed)) % len(patterns)]

    today_str = datetime.now().strftime("%m月%d日")
    results = {}

    for blogger_name, style in styles.items():
        openings = style.get("top_openings", [])
        endings = style.get("top_endings", [])
        transitions = style.get("vocabulary", {}).get("transitions", [])
        emotions = style.get("vocabulary", {}).get("emotions", [])
        interactions = style.get("vocabulary", {}).get("interactions", [])

        opening = pick(openings, topic + blogger_name) if openings else ""
        ending = pick(endings, topic + blogger_name + "end") if endings else ""
        transition = pick(transitions, topic + blogger_name + "trans") if transitions else "不过"
        emotion = pick(emotions, topic + blogger_name + "emo") if emotions else "有意思"
        interaction = pick(interactions, topic + blogger_name + "inter") if interactions else "你们"

        # 清理开头中的具体名词
        opening = re.sub(r'\d{4}年\d{1,2}月\d{1,2}日', today_str, opening)
        opening = re.sub(r'\d{1,2}月\d{1,2}日', today_str, opening)

        if blogger_name == "网吧信息差":
            content = f"{opening}{topic}。这事儿一出来，网友们直接就绷不住了。{transition}，有人说这也太{emotion}了，有人说这背后肯定有故事。但不管怎么说，这事儿确实挺{emotion}的。{interaction}遇到过类似的事吗？评论区分享一下。"
        elif blogger_name == "阿七大型纪录片":
            content = f"热点信息差，{topic}。这事儿一出来，网友们直接就炸锅了。{transition}，有人说这也太{emotion}了，有人说这背后肯定有隐情。但不管怎么说，这事儿确实挺{emotion}的。{interaction}遇到过类似的事吗？评论区分享一下。"
        elif blogger_name == "陈先生":
            content = f"{topic}。这事儿一出来，直接把网友们整不会了。{transition}，有人说这也太{emotion}了，有人说这背后肯定有故事。{interaction}怎么看？评论区聊聊。"
        elif blogger_name == "人类观察菌":
            content = f"今日热点信息快报。{topic}。这事儿一出来，网友们直接就炸锅了。{transition}，有人说这也太{emotion}了，有人说这背后肯定有隐情。但不管怎么说，这事儿确实挺{emotion}的。{interaction}遇到过类似的事吗？评论区分享一下。"
        elif blogger_name == "沙漠一之雕":
            content = f"一夜之间发生了啥？{today_str}热点快报。第一条——{topic}。起因很简单，但后面发生的事完全出乎意料。事情是这样的：最早是——结果没过多久——然后今天上午——。大家现在最关心的问题是——这个问题的答案可能比你想的复杂。来评论区一人一句。"
        else:
            content = f"{opening}{topic}。{ending}"

        results[blogger_name] = content

    return results


def main():
    """主函数"""
    print("=== 持续学习系统 ===\n")

    # 1. 归档当前文案
    archive = archive_content()

    # 2. 从归档中学习
    styles = learn_from_archive()

    if not styles:
        print("没有足够的样本数据")
        return

    # 3. 显示学习统计
    print("\n=== 学习统计 ===")
    for name, style in styles.items():
        print(f"  {name}: {style['sample_count']}条样本, 平均{style['avg_length']}字")
        print(f"    转折词: {style['vocabulary'].get('transitions', [])[:5]}")
        print(f"    情感词: {style['vocabulary'].get('emotions', [])[:5]}")

    print("\n✅ 学习完成！下次运行 auto_run.bat 时会自动使用新的学习结果。")


if __name__ == "__main__":
    main()
