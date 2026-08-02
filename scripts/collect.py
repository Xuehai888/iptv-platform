#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPTV Source Collector v2 - Enhanced Chinese Sources
"""
import os
import re
import time
import logging
from datetime import datetime
from urllib.request import urlopen, Request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = "/opt/iptv"
M3U_DIR = os.path.join(BASE_DIR, "m3u")
TXT_DIR = os.path.join(BASE_DIR, "txt")
LOG_DIR = os.path.join(BASE_DIR, "logs")
TIMEOUT = 8
MAX_WORKERS = 30

# More sources, especially Chinese
SOURCES = [
    # === iptv-org (global) ===
    "https://iptv-org.github.io/iptv/index.m3u",
    "https://iptv-org.github.io/iptv/languages/zho.m3u",
    "https://iptv-org.github.io/iptv/countries/cn.m3u",
    "https://iptv-org.github.io/iptv/countries/hk.m3u",
    "https://iptv-org.github.io/iptv/countries/tw.m3u",
    "https://iptv-org.github.io/iptv/countries/mo.m3u",
    # === Free-TV ===
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
    # === YanG-1989 (Chinese IPTV) ===
    "https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u",
    # === Guovin (Chinese IPTV) ===
    "https://raw.githubusercontent.com/guovin/iptv/main/result.txt",
    # === vbskycn ===
    "https://raw.githubusercontent.com/vbskycn/iptv/master/tv.txt",
    # === fanmingming ===
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/global.m3u",
    # === best-fan ===
    "https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_all.m3u8",
    # === jia070310 4K ===
    "https://raw.githubusercontent.com/jia070310/4K-IPTV-M3U/main/m3u/all.m3u",
]

CN_KEYWORDS = [
    "CCTV", "央视", "卫视", "TVB", "凤凰", "芒果", "湖南",
    "浙江", "江苏", "北京", "东方", "广东", "深圳", "四川",
    "湖北", "辽宁", "山东", "河南", "福建", "安徽", "天津",
    "重庆", "陕西", "河北", "山西", "吉林", "黑龙江", "江西",
    "广西", "云南", "贵州", "甘肃", "内蒙古", "新疆", "西藏",
    "青海", "宁夏", "海南", "香港", "澳门", "台湾",
    "CHC", "CGTN", "大湾区", "东南", "海峡", "厦门",
    "珠江", "南方", "综艺", "体育", "新闻", "电影", "电视剧",
    "纪录", "少儿", "卡通", "动画", "音乐", "财经", "军事",
    "教育", "科技", "文化", "旅游", "生活", "健康", "法治",
    "综合", "公共", "都市", "经济", "民生", "社会", "法制",
    "娱乐", "影视", "戏剧", "戏曲", "经典", "怀旧",
    "广东", "广州", "佛山", "东莞", "中山", "珠海", "惠州",
    "汕头", "潮州", "揭阳", "梅州", "河源", "清远", "韶关",
    "肇庆", "云浮", "阳江", "茂名", "湛江",
    "上海", "浙江", "江苏", "安徽", "山东", "河南", "湖北",
    "湖南", "福建", "四川", "重庆", "云南", "贵州", "广西",
    "北京", "天津", "河北", "山西", "内蒙古",
    "辽宁", "吉林", "黑龙江",
    "陕西", "甘肃", "青海", "宁夏", "新疆",
    "江西", "海南", "西藏",
    "港台", "TVB", "ATV", "Viu", "RTHK",
    "中天", "三立", "民视", "华视", "台视", "大爱",
    "东森", "纬来", "壹电视", "年代", "TVBS",
    "中视", "公视", "原住", "客家",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "collect.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


def fetch_url(url, timeout=20):
    headers = {"User-Agent": "Mozilla/5.0 IPTV-Collector/2.0"}
    for attempt in range(3):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            if attempt == 2:
                log.warning(f"Failed to fetch {url}: {e}")
                return None
            time.sleep(2)
    return None


def parse_m3u(content):
    channels = []
    if not content:
        return channels
    lines = content.strip().split("\n")
    current = {}
    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF:"):
            match = re.search(r'#EXTINF:-?\d+\s*(?:[a-z-]+="[^"]*"\s*)*,(.+)', line)
            name = match.group(1).strip() if match else "Unknown"
            logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            logo = logo_match.group(1) if logo_match else ""
            group_match = re.search(r'group-title="([^"]*)"', line)
            group = group_match.group(1) if group_match else "Other"
            current = {"name": name, "logo": logo, "group": group}
        elif line and not line.startswith("#"):
            current["url"] = line
            if "name" in current:
                channels.append(current)
            current = {}
    return channels


def parse_txt(content):
    """Parse TXT format (group,#genre# then name,url)"""
    channels = []
    if not content:
        return channels
    current_group = "Other"
    for line in content.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ",#genre#" in line:
            current_group = line.replace(",#genre#", "").strip()
        elif "," in line:
            parts = line.split(",", 1)
            if len(parts) == 2:
                name = parts[0].strip()
                url = parts[1].strip()
                if url.startswith("http"):
                    channels.append({
                        "name": name,
                        "url": url,
                        "group": current_group,
                        "logo": ""
                    })
    return channels


def validate_channel(channel):
    url = channel.get("url", "")
    if not url:
        return False
    try:
        req = Request(url, method="HEAD", headers={"User-Agent": "VLC/3.0"})
        with urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status in (200, 301, 302)
    except Exception:
        try:
            req = Request(url, headers={
                "User-Agent": "VLC/3.0",
                "Range": "bytes=0-1024"
            })
            with urlopen(req, timeout=TIMEOUT) as resp:
                return resp.status in (200, 206, 301, 302)
        except Exception:
            return False


def is_chinese_channel(channel):
    name = channel.get("name", "")
    group = channel.get("group", "")
    text = (name + " " + group).upper()
    return any(kw.upper() in text for kw in CN_KEYWORDS)


def generate_m3u(channels, title="IPTV"):
    lines = ["#EXTM3U"]
    for ch in channels:
        logo = ch.get("logo", "")
        group = ch.get("group", "Other")
        name = ch.get("name", "Unknown")
        url = ch.get("url", "")
        logo_attr = f' tvg-logo="{logo}"' if logo else ""
        lines.append(f'#EXTINF:-1 tvg-group="{group}"{logo_attr},{name}')
        lines.append(url)
    return "\n".join(lines)


def generate_txt(channels):
    lines = []
    groups = {}
    for ch in channels:
        g = ch.get("group", "Other")
        if g not in groups:
            groups[g] = []
        groups[g].append(ch)
    for group, chs in sorted(groups.items()):
        lines.append(f"{group},#genre#")
        for ch in chs:
            lines.append(f"{ch['name']},{ch['url']}")
        lines.append("")
    return "\n".join(lines)


def classify_channel(name):
    """Classify channel into a better group"""
    name_upper = name.upper()
    if any(k in name_upper for k in ["CCTV", "央视"]):
        return "📺 央视频道"
    if any(k in name_upper for k in ["卫视"]):
        return "📺 卫视频道"
    if any(k in name_upper for k in ["TVB", "凤凰", "香港", "RTHK", "Viu"]):
        return "🇭🇰 港台频道"
    if any(k in name_upper for k in ["中天", "三立", "民视", "华视", "台视", "东森", "纬来", "TVBS", "中视", "公视"]):
        return "🇹🇼 台湾频道"
    if any(k in name_upper for k in ["CGTN", "NEWS", "新闻", "CNN", "BBC"]):
        return "📰 新闻频道"
    if any(k in name_upper for k in ["体育", "SPORT"]):
        return "⚽ 体育频道"
    if any(k in name_upper for k in ["电影", "MOVIE", "HBO", "CINEMAX"]):
        return "🎬 电影频道"
    if any(k in name_upper for k in ["音乐", "MUSIC", "MTV"]):
        return "🎵 音乐频道"
    if any(k in name_upper for k in ["纪录", "DOCUMENTARY", "DISCOVERY", "NATGEO"]):
        return "📖 纪录频道"
    if any(k in name_upper for k in ["少儿", "卡通", "动画", "KIDS", "CARTOON"]):
        return "🧒 少儿频道"
    if any(k in name_upper for k in ["财经", "FINANCE", "BUSINESS"]):
        return "💰 财经频道"
    # Province classification
    provinces = ["广东", "广州", "深圳", "上海", "北京", "浙江", "江苏",
                 "湖南", "湖北", "四川", "重庆", "山东", "河南", "福建",
                 "安徽", "天津", "陕西", "河北", "山西", "辽宁", "吉林",
                 "黑龙江", "江西", "云南", "贵州", "广西", "海南",
                 "甘肃", "内蒙古", "新疆", "西藏", "青海", "宁夏"]
    for p in provinces:
        if p in name:
            return f"🏠 {p}频道"
    return "📺 其他频道"


def main():
    start_time = time.time()
    log.info("=" * 50)
    log.info("IPTV Collection v2 started")
    log.info("=" * 50)

    all_channels = []
    for src_url in SOURCES:
        log.info(f"Fetching: {src_url}")
        content = fetch_url(src_url, timeout=25)
        if content:
            # Auto-detect format
            if content.strip().startswith("#EXTM3U") or "#EXTINF" in content[:500]:
                channels = parse_m3u(content)
            else:
                channels = parse_txt(content)
            log.info(f"  Parsed {len(channels)} channels")
            all_channels.extend(channels)

    log.info(f"Total raw channels: {len(all_channels)}")

    # Deduplicate by URL
    seen_urls = set()
    unique_channels = []
    for ch in all_channels:
        url = ch.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_channels.append(ch)
    log.info(f"Unique channels: {len(unique_channels)}")

    # Filter Chinese channels
    cn_channels = [ch for ch in unique_channels if is_chinese_channel(ch)]
    log.info(f"Chinese channels found: {len(cn_channels)}")

    # Validate Chinese channels
    log.info(f"Validating {len(cn_channels)} Chinese channels...")
    valid_cn = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(validate_channel, ch): ch for ch in cn_channels}
        done = 0
        for future in as_completed(futures):
            done += 1
            ch = futures[future]
            try:
                if future.result():
                    valid_cn.append(ch)
            except Exception:
                pass
            if done % 100 == 0:
                log.info(f"  Progress: {done}/{len(cn_channels)}, valid: {len(valid_cn)}")

    log.info(f"Valid Chinese channels: {len(valid_cn)}")

    # If too few valid, add unvalidated Chinese as backup
    if len(valid_cn) < 30:
        log.warning("Few valid channels, adding unvalidated as backup")
        valid_urls = {ch["url"] for ch in valid_cn}
        for ch in cn_channels:
            if ch["url"] not in valid_urls:
                valid_cn.append(ch)

    # Reclassify channels
    for ch in valid_cn:
        ch["group"] = classify_channel(ch["name"])

    # International channels (unvalidated, just deduplicated)
    intl_channels = [ch for ch in unique_channels if not is_chinese_channel(ch)]
    log.info(f"International channels: {len(intl_channels)}")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # === Output files ===

    # 1. Chinese M3U
    cn_m3u = f"#EXTM3U\n# Generated: {timestamp}\n# Chinese Channels: {len(valid_cn)}\n"
    cn_m3u += generate_m3u(valid_cn)
    with open(os.path.join(M3U_DIR, "cn.m3u"), "w", encoding="utf-8") as f:
        f.write(cn_m3u)

    # 2. Chinese TXT
    cn_txt = generate_txt(valid_cn)
    with open(os.path.join(TXT_DIR, "cn.txt"), "w", encoding="utf-8") as f:
        f.write(cn_txt)

    # 3. All M3U
    all_output = valid_cn + intl_channels
    all_m3u = f"#EXTM3U\n# Generated: {timestamp}\n# Total: {len(all_output)}\n"
    all_m3u += generate_m3u(all_output)
    with open(os.path.join(M3U_DIR, "all.m3u"), "w", encoding="utf-8") as f:
        f.write(all_m3u)

    # 4. All TXT
    all_txt = generate_txt(all_output)
    with open(os.path.join(TXT_DIR, "all.txt"), "w", encoding="utf-8") as f:
        f.write(all_txt)

    # 5. CCTV only
    cctv = [ch for ch in valid_cn if "CCTV" in ch["name"].upper() or "央视" in ch["name"]]
    cctv_m3u = f"#EXTM3U\n# CCTV Channels: {len(cctv)}\n"
    cctv_m3u += generate_m3u(cctv)
    with open(os.path.join(M3U_DIR, "cctv.m3u"), "w", encoding="utf-8") as f:
        f.write(cctv_m3u)

    # 6. Weishi only
    weishi = [ch for ch in valid_cn if "卫视" in ch["name"]]
    ws_m3u = f"#EXTM3U\n# Weishi Channels: {len(weishi)}\n"
    ws_m3u += generate_m3u(weishi)
    with open(os.path.join(M3U_DIR, "weishi.m3u"), "w", encoding="utf-8") as f:
        f.write(ws_m3u)

    # 7. Index page
    index_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>📺 IPTV Source Station</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: -apple-system, 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        h1 {{ color: #1a1a2e; text-align: center; }}
        .subtitle {{ text-align: center; color: #666; margin-bottom: 30px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 20px; }}
        .card {{ background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .card h3 {{ margin-top: 0; color: #16213e; border-bottom: 2px solid #e94560; padding-bottom: 8px; }}
        .card p {{ margin: 8px 0; }}
        a {{ color: #0066cc; }}
        .url {{ background: #f0f0f0; padding: 8px 12px; border-radius: 6px; font-family: monospace; font-size: 0.85em; word-break: break-all; display: block; margin: 8px 0; }}
        .badge {{ display: inline-block; background: #e94560; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.8em; }}
        .footer {{ text-align: center; color: #999; margin-top: 30px; font-size: 0.85em; }}
    </style>
</head>
<body>
    <h1>📺 IPTV Source Station</h1>
    <p class="subtitle">Last updated: {timestamp} | Auto-refresh every 6 hours</p>

    <div class="grid">
        <div class="card">
            <h3>🇨🇳 中文频道 ({len(valid_cn)})</h3>
            <p>M3U 格式 <span class="badge">推荐</span></p>
            <span class="url">http://207.246.102.108/m3u/cn.m3u</span>
            <p>TXT 格式 (TVBox兼容)</p>
            <span class="url">http://207.246.102.108/txt/cn.txt</span>
        </div>

        <div class="card">
            <h3>📺 CCTV 央视 ({len(cctv)})</h3>
            <p>M3U 格式</p>
            <span class="url">http://207.246.102.108/m3u/cctv.m3u</span>
        </div>

        <div class="card">
            <h3>📺 卫视频道 ({len(weishi)})</h3>
            <p>M3U 格式</p>
            <span class="url">http://207.246.102.108/m3u/weishi.m3u</span>
        </div>

        <div class="card">
            <h3>🌍 全球频道 ({len(all_output)})</h3>
            <p>M3U 格式</p>
            <span class="url">http://207.246.102.108/m3u/all.m3u</span>
            <p>TXT 格式</p>
            <span class="url">http://207.246.102.108/txt/all.txt</span>
        </div>
    </div>

    <div class="card" style="margin-top: 20px;">
        <h3>📖 使用说明</h3>
        <p><strong>VLC / PotPlayer:</strong> 媒体 → 打开网络串流 → 粘贴 M3U 链接</p>
        <p><strong>TVBox / FongMi:</strong> 设置 → 配置地址 → 粘贴 TXT 链接</p>
        <p><strong>TiviMate / APTV:</strong> 添加播放列表 → 粘贴 M3U 链接</p>
        <p><strong>Jellyfin:</strong> 直播电视 → 添加频道源 → M3U 链接</p>
    </div>

    <p class="footer">Powered by iptv-org + custom collector | For educational purposes only</p>
</body>
</html>"""
    with open(os.path.join(BASE_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    elapsed = time.time() - start_time
    log.info(f"Done in {elapsed:.1f}s")
    log.info(f"Chinese: {len(valid_cn)} | CCTV: {len(cctv)} | Weishi: {len(weishi)} | All: {len(all_output)}")


if __name__ == "__main__":
    main()
