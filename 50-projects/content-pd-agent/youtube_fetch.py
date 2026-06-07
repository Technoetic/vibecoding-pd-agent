#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
양실장 바이브코딩대학 채널 영상 카탈로그 갱신 — channel_catalog.json 생성.
YouTube Data API v3, 표준 라이브러리만(의존성 0).

실행:  YOUTUBE_API_KEY=... python youtube_fetch.py
"""
import os, json, urllib.request
from pathlib import Path

KEY = os.environ.get("YOUTUBE_API_KEY", "")
HANDLE = "@VibecodingUniversity"
BASE = "https://www.googleapis.com/youtube/v3"
OUT = Path(__file__).resolve().parent / "channel_catalog.json"


def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    if not KEY:
        raise SystemExit("[!] YOUTUBE_API_KEY 미설정")
    ch = get(f"{BASE}/channels?part=snippet,statistics,contentDetails&forHandle={HANDLE}&key={KEY}")
    item = ch["items"][0]
    uploads = item["contentDetails"]["relatedPlaylists"]["uploads"]
    title = item["snippet"]["title"]

    videos, page = [], ""
    while True:
        url = f"{BASE}/playlistItems?part=snippet,contentDetails&maxResults=50&playlistId={uploads}&key={KEY}"
        if page:
            url += f"&pageToken={page}"
        d = get(url)
        for it in d.get("items", []):
            sn = it["snippet"]
            videos.append({
                "video_id": it["contentDetails"]["videoId"],
                "title": sn["title"],
                "published": sn.get("publishedAt", "")[:10],
            })
        page = d.get("nextPageToken")
        if not page:
            break

    ids = [v["video_id"] for v in videos]
    for i in range(0, len(ids), 50):
        d = get(f"{BASE}/videos?part=statistics&id={','.join(ids[i:i+50])}&key={KEY}")
        stat = {it["id"]: int(it.get("statistics", {}).get("viewCount", 0) or 0) for it in d.get("items", [])}
        for v in videos:
            if v["video_id"] in stat:
                v["views"] = stat[v["video_id"]]

    videos.sort(key=lambda x: x["published"], reverse=True)
    cache = {
        "channel": title, "handle": HANDLE, "channel_id": item["id"],
        "fetched_count": len(videos), "videos": videos,
    }
    OUT.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"SAVED {OUT.name}: {len(videos)} videos")


if __name__ == "__main__":
    main()
