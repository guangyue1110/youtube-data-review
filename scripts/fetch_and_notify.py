#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Shorts 数据抓取脚本
用于 GitHub Actions 定时运行，自动创建 Issue 报告
"""

import os
import json
import urllib.request
from datetime import datetime
from pathlib import Path


def make_api_request(url: str) -> dict:
    """发送 API 请求"""
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"API 请求错误: {e}")
        return {}


def get_latest_shorts(api_key: str, channel_id: str, max_results: int = 5) -> list:
    """获取频道最新的 Shorts 视频"""
    base_url = "https://www.googleapis.com/youtube/v3"
    import re

    # 1. 获取频道上传播放列表 ID
    channel_url = f"{base_url}/channels?part=contentDetails&id={channel_id}&key={api_key}"
    channel_response = make_api_request(channel_url)

    if not channel_response.get('items'):
        return []

    uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

    # 2. 获取最新视频
    playlist_url = f"{base_url}/playlistItems?part=snippet,contentDetails&playlistId={uploads_playlist_id}&maxResults={max_results}&key={api_key}"
    playlist_response = make_api_request(playlist_url)

    if not playlist_response.get('items'):
        return []

    # 3. 获取视频详情
    video_ids = [item['contentDetails']['videoId'] for item in playlist_response['items']]
    ids_param = ','.join(video_ids)

    videos_url = f"{base_url}/videos?part=snippet,contentDetails,statistics&id={ids_param}&key={api_key}"
    videos_response = make_api_request(videos_url)

    shorts = []
    for video in videos_response.get('items', []):
        # 解析时长
        duration_str = video['contentDetails']['duration']
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
        if match:
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            duration = hours * 3600 + minutes * 60 + seconds
        else:
            duration = 0

        # 只保留 Shorts (<=60秒)
        if duration <= 60:
            stats = video.get('statistics', {})
            shorts.append({
                'id': video['id'],
                'title': video['snippet']['title'][:50],
                'published_at': video['snippet']['publishedAt'],
                'duration': duration,
                'views': int(stats.get('viewCount', 0)),
                'likes': int(stats.get('likeCount', 0)),
                'comments': int(stats.get('commentCount', 0)),
                'url': f"https://youtube.com/shorts/{video['id']}"
            })

    return shorts


def format_number(n):
    """格式化数字"""
    if n >= 1000000:
        return f"{n/1000000:.1f}M"
    elif n >= 1000:
        return f"{n/1000:.1f}K"
    return str(n)


def generate_issue_body(data_a: list, data_b: list) -> str:
    """生成 Issue Markdown 内容"""

    latest_a = data_a[0] if data_a else None
    latest_b = data_b[0] if data_b else None

    today = datetime.now().strftime('%Y-%m-%d')
    time_now = datetime.now().strftime('%H:%M')

    # 计算差异
    if latest_a and latest_b and latest_b['views'] > 0:
        views_diff = ((latest_a['views'] - latest_b['views']) / latest_b['views'] * 100)
        likes_diff = ((latest_a['likes'] - latest_b['likes']) / latest_b['likes'] * 100) if latest_b['likes'] > 0 else 0
    else:
        views_diff = 0
        likes_diff = 0

    # 判断胜出方
    winner = "A" if views_diff > 0 else "B" if views_diff < 0 else "持平"

    md = f"""# 📊 YouTube 数据复盘

**日期**: {today}
**抓取时间**: {time_now}
**AB 测试结果**: 🏆 **{winner} 频道胜出**

---

## 🅰️ A 频道最新视频

| 项目 | 数据 |
|------|------|
| 标题 | {latest_a['title'] if latest_a else '暂无数据'} |
| 播放量 | {format_number(latest_a['views']) if latest_a else '-'} |
| 点赞数 | {format_number(latest_a['likes']) if latest_a else '-'} |
| 评论数 | {latest_a['comments'] if latest_a else '-'} |
| 时长 | {latest_a['duration']}s |
| 链接 | [查看视频]({latest_a['url'] if latest_a else '#'}) |

---

## 🅱️ B 频道最新视频

| 项目 | 数据 |
|------|------|
| 标题 | {latest_b['title'] if latest_b else '暂无数据'} |
| 播放量 | {format_number(latest_b['views']) if latest_b else '-'} |
| 点赞数 | {format_number(latest_b['likes']) if latest_b else '-'} |
| 评论数 | {latest_b['comments'] if latest_b else '-'} |
| 时长 | {latest_b['duration']}s |
| 链接 | [查看视频]({latest_b['url'] if latest_b else '#'}) |

---

## 📈 AB 测试对比

| 指标 | A 频道 | B 频道 | 差异 |
|------|--------|--------|------|
| 播放量 | {format_number(latest_a['views']) if latest_a else '-'} | {format_number(latest_b['views']) if latest_b else '-'} | **{'+' if views_diff >= 0 else ''}{views_diff:.0f}%** |
| 点赞数 | {format_number(latest_a['likes']) if latest_a else '-'} | {format_number(latest_b['likes']) if latest_b else '-'} | **{'+' if likes_diff >= 0 else ''}{likes_diff:.0f}%** |

---

## 💡 下一步

在 Claude Code 中输入「帮我做数据复盘」进行深度分析和经验提炼。

---

*此报告由 GitHub Actions 自动生成*
"""
    return md


def save_report(data_a: list, data_b: list) -> str:
    """保存报告到文件"""
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    today = datetime.now().strftime('%Y-%m-%d')
    report_path = reports_dir / f"{today}_report.json"

    report_data = {
        "date": today,
        "fetch_time": datetime.now().isoformat(),
        "channel_a": data_a,
        "channel_b": data_b
    }

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    # 生成 Issue Markdown
    issue_md = generate_issue_body(data_a, data_b)
    issue_path = reports_dir / "issue_body.md"
    with open(issue_path, 'w', encoding='utf-8') as f:
        f.write(issue_md)

    # 设置环境变量供 GitHub Actions 使用
    env_file = os.environ.get('GITHUB_ENV')
    if env_file:
        with open(env_file, 'a') as f:
            f.write(f"REPORT_DATE={today}\n")

    print(f"报告已保存: {report_path}")
    print(f"Issue 已生成: {issue_path}")
    return str(report_path)


def main():
    # 从环境变量获取配置
    api_key = os.environ.get('YOUTUBE_API_KEY')
    channel_a_id = os.environ.get('CHANNEL_A_ID')
    channel_b_id = os.environ.get('CHANNEL_B_ID')

    if not api_key:
        print("错误: 未设置 YOUTUBE_API_KEY")
        return

    if not channel_a_id or not channel_b_id:
        print("错误: 未设置频道 ID")
        return

    print("=" * 50)
    print("📊 YouTube Shorts 数据抓取")
    print("=" * 50)

    # 抓取数据
    print("\n抓取 A 频道数据...")
    data_a = get_latest_shorts(api_key, channel_a_id)
    print(f"✅ 获取 {len(data_a)} 个 Shorts")

    print("\n抓取 B 频道数据...")
    data_b = get_latest_shorts(api_key, channel_b_id)
    print(f"✅ 获取 {len(data_b)} 个 Shorts")

    # 保存报告
    save_report(data_a, data_b)

    print("\n✅ 数据复盘完成！")


if __name__ == '__main__':
    main()
