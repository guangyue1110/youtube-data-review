#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Shorts 数据抓取 + 邮件报告脚本
用于 GitHub Actions 定时运行
"""

import os
import json
import re
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

    # 1. 获取频道上传播放列表 ID
    channel_url = f"{base_url}/channels?part=contentDetails&id={channel_id}&key={api_key}"
    channel_response = make_api_request(channel_url)

    if not channel_response.get('items'):
        print(f"  频道 {channel_id} 未找到或请求失败")
        return []

    uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    print(f"  获取播放列表成功")

    # 2. 获取最新视频
    playlist_url = f"{base_url}/playlistItems?part=snippet,contentDetails&playlistId={uploads_playlist_id}&maxResults={max_results}&key={api_key}"
    playlist_response = make_api_request(playlist_url)

    if not playlist_response.get('items'):
        print(f"  播放列表为空")
        return []

    print(f"  获取 {len(playlist_response['items'])} 个视频")

    # 3. 获取视频详情
    video_ids = [item['contentDetails']['videoId'] for item in playlist_response['items']]
    ids_param = ','.join(video_ids)

    videos_url = f"{base_url}/videos?part=snippet,contentDetails,statistics&id={ids_param}&key={api_key}"
    videos_response = make_api_request(videos_url)

    shorts = []
    for video in videos_response.get('items', []):
        duration_str = video['contentDetails']['duration']
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
        if match:
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            duration = hours * 3600 + minutes * 60 + seconds
        else:
            duration = 0

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

    print(f"  筛选出 {len(shorts)} 个 Shorts")
    return shorts


def format_number(n):
    if n >= 1000000:
        return f"{n/1000000:.1f}M"
    elif n >= 1000:
        return f"{n/1000:.1f}K"
    return str(n)


def generate_email_html(data_a: list, data_b: list) -> str:
    """生成邮件 HTML"""
    latest_a = data_a[0] if data_a else None
    latest_b = data_b[0] if data_b else None

    today = datetime.now().strftime('%Y-%m-%d')
    time_now = datetime.now().strftime('%H:%M')

    if latest_a and latest_b and latest_b['views'] > 0:
        views_diff = ((latest_a['views'] - latest_b['views']) / latest_b['views'] * 100)
        likes_diff = ((latest_a['likes'] - latest_b['likes']) / latest_b['likes'] * 100) if latest_b['likes'] > 0 else 0
    else:
        views_diff = 0
        likes_diff = 0

    winner = "A" if views_diff > 0 else "B" if views_diff < 0 else "平手"

    a_title = latest_a['title'] if latest_a else '暂无数据'
    a_views = format_number(latest_a['views']) if latest_a else '-'
    a_likes = format_number(latest_a['likes']) if latest_a else '-'
    a_comments = str(latest_a['comments']) if latest_a else '-'
    a_duration = f"{latest_a['duration']}s" if latest_a else '-'
    a_url = latest_a['url'] if latest_a else '#'

    b_title = latest_b['title'] if latest_b else '暂无数据'
    b_views = format_number(latest_b['views']) if latest_b else '-'
    b_likes = format_number(latest_b['likes']) if latest_b else '-'
    b_comments = str(latest_b['comments']) if latest_b else '-'
    b_duration = f"{latest_b['duration']}s" if latest_b else '-'
    b_url = latest_b['url'] if latest_b else '#'

    views_diff_str = f"+{views_diff:.0f}%" if views_diff >= 0 else f"{views_diff:.0f}%"
    likes_diff_str = f"+{likes_diff:.0f}%" if likes_diff >= 0 else f"{likes_diff:.0f}%"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family: -apple-system, sans-serif; background: #f5f5f5; padding: 20px;">
<div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden;">

<div style="background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 24px; text-align: center;">
<h1 style="margin: 0;">📊 YouTube 数据复盘</h1>
<p style="margin: 8px 0 0; opacity: 0.9;">{today} {time_now}</p>
<p style="margin: 4px 0 0;">AB 测试结果: 🏆 {winner} 频道胜出</p>
</div>

<div style="padding: 24px;">

<div style="background: #f8f9fa; border-radius: 8px; padding: 16px; margin-bottom: 16px; border-left: 4px solid #667eea;">
<h3 style="margin: 0 0 8px;">🅰️ A 频道最新视频</h3>
<p style="margin: 0 0 8px;">{a_title}</p>
<p style="margin: 0;">▶️ {a_views} &nbsp; 👍 {a_likes} &nbsp; 💬 {a_comments} &nbsp; ⏱️ {a_duration}</p>
<a href="{a_url}" style="color: #667eea;">查看视频 →</a>
</div>

<div style="background: #f8f9fa; border-radius: 8px; padding: 16px; margin-bottom: 16px; border-left: 4px solid #f093fb;">
<h3 style="margin: 0 0 8px;">🅱️ B 频道最新视频</h3>
<p style="margin: 0 0 8px;">{b_title}</p>
<p style="margin: 0;">▶️ {b_views} &nbsp; 👍 {b_likes} &nbsp; 💬 {b_comments} &nbsp; ⏱️ {b_duration}</p>
<a href="{b_url}" style="color: #764ba2;">查看视频 →</a>
</div>

<div style="background: linear-gradient(135deg, #667eea, #764ba2); color: white; border-radius: 8px; padding: 16px;">
<h3 style="margin: 0 0 12px;">📈 AB 测试对比</h3>
<div style="display: flex; gap: 12px;">
<div style="flex: 1; background: rgba(255,255,255,0.2); border-radius: 6px; padding: 12px; text-align: center;">
<div style="font-size: 24px; font-weight: bold;">{views_diff_str}</div>
<div style="font-size: 12px;">播放量差异</div>
</div>
<div style="flex: 1; background: rgba(255,255,255,0.2); border-radius: 6px; padding: 12px; text-align: center;">
<div style="font-size: 24px; font-weight: bold;">{likes_diff_str}</div>
<div style="font-size: 12px;">点赞数差异</div>
</div>
</div>
</div>

<p style="text-align: center; color: #666; margin-top: 16px;">💡 在 Claude Code 中输入「帮我做数据复盘」进行深度分析</p>

</div>

<div style="text-align: center; padding: 16px; color: #999; font-size: 12px; border-top: 1px solid #eee;">
由 GitHub Actions 自动发送
</div>

</div>
</body></html>"""
    return html


def main():
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

    print("\n抓取 A 频道数据...")
    data_a = get_latest_shorts(api_key, channel_a_id)
    print(f"✅ 获取 {len(data_a)} 个 Shorts")

    print("\n抓取 B 频道数据...")
    data_b = get_latest_shorts(api_key, channel_b_id)
    print(f"✅ 获取 {len(data_b)} 个 Shorts")

    # 保存
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    today = datetime.now().strftime('%Y-%m-%d')

    # 保存 JSON
    report_data = {
        "date": today,
        "fetch_time": datetime.now().isoformat(),
        "channel_a": data_a,
        "channel_b": data_b
    }
    with open(reports_dir / f"{today}_report.json", 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    # 生成邮件 HTML
    email_html = generate_email_html(data_a, data_b)
    with open(reports_dir / "email_body.html", 'w', encoding='utf-8') as f:
        f.write(email_html)

    # 设置环境变量
    env_file = os.environ.get('GITHUB_ENV')
    if env_file:
        with open(env_file, 'a') as f:
            f.write(f"REPORT_DATE={today}\n")

    print(f"\n✅ 数据复盘完成！")


if __name__ == '__main__':
    main()
